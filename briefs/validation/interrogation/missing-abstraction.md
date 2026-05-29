# Interrogation — MISSING ABSTRACTION lens

**Lens:** What abstraction does this plan LACK that it will discover too late and have to
retrofit painfully? Verdict written assuming we WILL do all of M1–M6 at full ambition.
Read: EPIC + m2/m3/m4/m5/m6 briefs; code-grounded in `megaplan/_pipeline/{types,pattern_types,
executor,builder,step_helpers,pattern_dynamic}.py`.

---

## THE single missing abstraction: a typed **Port / data-dependency contract** between pieces

The whole epic is "compose pieces." But there is **no typed contract for what flows between two
composed pieces** — what a step *produces* and what the next step *consumes*. Today inter-step
data flows through exactly three untyped, convention-based channels, and the EPIC adds zero
abstraction over any of them:

1. **The shared `state` dict.** `executor.py:257-258` does `state.update(dict(result.state_patch))`
   — a single flat namespace, last-writer-wins, no schema, no producer/consumer declaration. Every
   step can clobber every other step's keys. `pattern_dynamic._extract_specs_from_result`
   (`pattern_dynamic.py:52-58`) reaches into `state_patch["specs"]` by a hard-coded string key — the
   *only* contract between a generative reduce and the fan-out it feeds is the literal `"specs"`.
2. **`StepResult.outputs: Mapping[str, Path]`** — label→path, existence-checked only
   (`executor.py:255`, `_verify_outputs`). No type, no schema for the file content.
3. **`StepContext.inputs: Mapping[str, Path]`** — *and here is the smoking gun*: **the executor
   never binds `inputs` from a predecessor's `outputs`.** `inputs` is set once at pipeline entry
   (`run_cli.py:316-324`) and `dataclasses.replace(ctx, state=state)` at `executor.py:241` refreshes
   only `state`, never `inputs`. So a downstream step's declared inputs are resolved by
   **filesystem path-guessing convention** in `step_helpers.resolve_inputs` (`step_helpers.py:66-106`):
   `stage_id → <plan_dir>/<stage_id>/v<N>.<ext>`, `stage_id.* → reviewer-order glob`, and — the part
   that will bite — a **silent fallback** at `step_helpers.py:104`:
   `resolved[ref] = ctx.plan_dir / ref / "v1.md"` for a ref that was *never produced*. A typo'd or
   reordered dependency does not fail at composition time; it hands the consumer a path to a file
   that may not exist, deferred to a read error deep inside the step.

The builder's own docstring already gestures at the abstraction that is missing. `builder.py:11-13`
advertises a declarative wiring DSL — `.panel("panel_review", inputs=["draft"])`,
`.agent("synth", inputs=["panel_review.*"])`, `.agent("revise", inputs=["draft", "synth"])` — i.e.
**named data dependencies between stages**. But `agent()` (`builder.py:130-155`) just stores those
strings as `_input_refs` and `panel()` stashes `_panel_reviewer_order` (`builder.py:192`); nothing
validates that `"synth"` is a stage that exists, that it *produces* what `revise` *consumes*, or
that the dependency graph is acyclic/well-ordered. **The wiring layer is aspirational sugar over an
untyped convention.** jokes/doc/planning all get away with it because they are linear
forward-only chains where "the previous stage's output dir" is unambiguous.

### Why this is THE one (not the others on the candidate list)

The prompt's candidate list (no wiring layer, no versioning, no error-propagation model, no
dependency declaration) is real, but they are all **downstream of this one**. You cannot version a
piece's contract, declare a dependency on it, or propagate a typed failure across a composition if
there is no typed thing — a **Port** — that names *what a piece consumes and produces*. The Port is
the noun all the other missing abstractions are verbs about.

### Where it bites, milestone by milestone (this is the "discovered too late" part)

- **M2 makes it WORSE before anyone notices.** M2's headline win is `Reduce[T]` returning structured
  *data* instead of a `GateRecommendation`, and a **generative** reduce whose output is "the next
  `fan_out`'s input spec list" (m2 brief W3, EPIC:65-70). But the channel that generative reduce
  uses is *still* the string key `state_patch["specs"]` read by `pattern_dynamic.py:52`. So M2
  introduces a *typed value* `T` and then immediately **launders it back through an untyped dict key**
  to get it to the consumer. The `[T]` in `Reduce[T]` is a lie at the composition boundary: the type
  is known inside the reduce and erased the instant it crosses to the fan-out. m2's tournament toy
  (DC#6) will pass *because the author wrote both ends*; it proves nothing about a contract.
- **M3's `restore_and_diverge(version)` has no typed cursor.** Gate-consequence parameterization
  (m3 brief, gate consequence #3) lets a verdict route to `restore_and_diverge(version)`. But what is
  `version`? A snapshot id read from where in `state`? The state-evolution axis (snapshot/restore)
  and the gate consequence are designed in the same milestone yet there is no typed handle that says
  "this gate's consequence consumes a `version_id` that *that* step produced." It will be another
  string key in the flat dict.
- **M5 unifies three fan-out substrates with three different reduce shapes and no common Port.**
  m5 F2 (Open question #3) literally asks: "Prep reduces to research findings; critique to flag-ID
  sets; panel to `{reviewer}.{label}` paths… is one structured reduce type enough?" That open
  question *is* the missing abstraction surfacing. Without a Port type, "one `fan_out(items, invoke,
  reduce)`" unifies the *control flow* but each binding still emits a differently-shaped blob into
  the same untyped `state`/`outputs` channels, and the *next* stage still path-guesses. You will
  unify the verb and leave the data contract fragmented.
- **M6 is where it becomes unfixable cheaply.** M6 says "a fourth, non-planning tool ships on the
  identical parts" (acceptance #1) and "planning reads as composition" (#3). A `select`-tournament or
  a `run(cmd)`-oracle bisect is exactly the shape that does NOT have a tidy "previous stage's output
  dir" — bisect's oracle output (`{exit,stdout,stderr}`) must bind to the next iteration's *input
  range*; the tournament's `select` output (winners) must bind to the next round's *fan_out items*.
  With no Port, the fourth-tool author re-discovers `state["specs"]`-style string plumbing and
  filesystem path conventions by hand — i.e. **reinvents the wiring**, which is the exact symptom
  (EPIC:20-23 "resident bringing its own runner is the symptom the SDK exists to cure") the epic
  claims to be curing. The acceptance test ships, but it ships *because the author hand-wired the
  ports*, so it green-lights an SDK that hasn't actually removed the reinvention.

### What it should be

A **Port contract** as a first-class, frozen type, declared per node, and a **binder the driver
runs between steps** — not buried in `resolve_inputs` path-guessing:

- `Port = (name, kind: artifact|value|stream, schema: type|ContentType, cardinality: one|many|optional)`.
- A node declares `produces: tuple[Port,...]` and `consumes: tuple[Port,...]` (extends the `Step`
  Protocol at `types.py:167-183`, which today has only `name/kind/prompt_key/slot`).
- The **composition layer** (the builder + a new validator) resolves `consumes` against upstream
  `produces` **at build time** — turning `builder.py`'s aspirational `inputs=[...]` into a checked
  data-dependency DAG. A missing/typo'd/mistyped dep fails `build()`, not a deep read.
- The **executor binds ports at runtime**: replace the path-guessing in `step_helpers.resolve_inputs`
  + the never-rebound `ctx.inputs` with the driver populating each step's `inputs` from the resolved
  upstream `outputs`/values. Kill the silent `v1.md` fallback (`step_helpers.py:104`).
- This is the *carrier* for the three other missing abstractions: **versioning** = a `version` field
  on the Port schema; **dependency declaration** = `consumes` *is* the declaration; **typed
  failure-propagation** = a Port can carry an error/sentinel variant (today
  `prep_research.research_sentinel`, m5 F2:82, is a per-binding hack) so a failed producer routes a
  typed failure to consumers instead of writing a missing file.

**Re-sequencing demand (do NOT defer):** the Port type must land in **M2**, alongside `Reduce[T]`
and `select`. M2 is already touching every join/reduce signature and `pattern_types.py`; that is the
one cheap moment to make the value `T` *typed across the boundary* instead of erased into
`state["specs"]`. If Port arrives in M5/M6 it is a retrofit through `executor.py`, `builder.py`,
`step_helpers.py`, `subloop.py` (child-on-copy state, `subloop.py:83`) and every already-extracted
binding — a rewrite of the exact code M5 just shipped.

---

## top_bites (severity-ordered)

1. **`ctx.inputs` is never bound from upstream `outputs`; data-flow is filesystem path-guessing with a
   silent fallback** — `executor.py:241` (refreshes only `state`), `step_helpers.py:66-106`
   (esp. silent `:104` fallback). CRITICAL. Forces: the composition layer is a fiction — pieces
   "connect" only by sharing a `plan_dir` convention, so the fourth-tool author reinvents wiring.

2. **`Reduce[T]`'s type is erased the instant it crosses to the consumer** — m2 W3 wires the
   generative reduce through `state_patch["specs"]` (`pattern_dynamic.py:52`), an untyped string key.
   HIGH. Forces: M2 ships a *typed* primitive over an *untyped* boundary; the `[T]` guarantee stops
   at the producer's return statement.

3. **No typed producer/consumer declaration on `Step`** — `Step` Protocol (`types.py:167-183`) carries
   `name/kind/prompt_key/slot` and nothing about data contract; `builder.py:11-13` *advertises* a
   wiring DSL it doesn't enforce. HIGH. Forces: build-time validation impossible; cycles, typos,
   shape-mismatches all defer to deep runtime read errors.

4. **`restore_and_diverge(version)` and the three fan-out reduce shapes have no shared Port** — m3
   gate-consequence #3; m5 F2 Open-question #3. MEDIUM. Forces: each milestone invents its own
   string-keyed channel into the flat `state` dict, so "unify the verb" leaves the data contract
   fragmented per binding.
