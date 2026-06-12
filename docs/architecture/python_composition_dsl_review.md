# Python Composition DSL — Review & Recommendations

A review of `python_composition_dsl_plan.md` from three independent lenses: compositional algebra & API ergonomics, type-system soundness, and runtime/lifecycle integrity. This document captures the principles that hold up, the issues that don't, and the concrete edits to make before P1 ships.

## Principles That Should Stand

These choices in the plan are sound and should remain load-bearing:

1. **`VibeWorkflow` stays canonical (SD-001).** Building authoring sugar over the existing IR is correct. A parallel IR would fork validation, compilation, and provenance with no payoff.
2. **Multi-stage Python orchestration as the mixing model (SD-004).** "Graph -> Python transform -> Graph" is honest about Comfy's serialization boundary. Trying to inject live Python into an active graph would inherit every Comfy runtime constraint without any of its guarantees.
3. **`ExternalPythonNode` as the *only* runtime Python escape (SD-005).** Naming the boundary explicitly, and keeping it distinct from authoring-time `@block`, is the right line — the question is enforcement (see Issue #4).
4. **GraphBuilder as backend, not authoring surface.** The reasons in the plan (no typed handles, no provenance, runtime coupling) are accurate.
5. **ComfyScript as import-only.** Spike evidence supports this; do not relitigate.
6. **Typed handles must be additive (SD-010), with `str(handle)` coercion for the legacy form.** Backward-compat-by-coercion is the right migration shape — but the coercion is itself a soundness hazard (Issue #3).
7. **Custom-node pinning by `git_commit_sha` with optional `source_sha256` (SD-006).** Distinguishing tree-hash from per-class content hash is correct and should not be conflated.
8. **Manual, iterative ready-template migration (SD-008).** A codemod here would burn risk for no execution gain.
9. **Provenance extends the existing `block`/`block_id`/`widget_kwargs` pattern upward** rather than replacing it.
10. **Phased rollout with `wf.run_until` gated on P4.** Refusing to promise inferred sinks before schema-backed `output_type` is the right discipline.

## Principles To Add

Drawn from gaps the plan does not currently make explicit:

- **One enforcement gate per documented invariant.** Every "shall not" in the plan needs a code-level check, or it should be downgraded to "convention." Documentation rules with no gate become folklore.
- **Escape hatches must round-trip into composition.** A one-way exit (raw API dict to runtime) is fine; a one-way exit *out of composition* (cannot become a `VibeFlow` Stage) creates a permanent two-class system.
- **Type-level claims must match what static checkers actually see.** A `Handle[T]` that carries useful runtime metadata is fine to ship — but if mypy/pyright will not flag a misuse, call it "typed metadata" rather than implying mypy-grade safety.
- **Lifecycle verbs must be named for what they do.** "session.stop() then session.start()" is not a contract for *nodepack reload* — it is a recipe. The contract needs its own verb, or the reload is not a guaranteed operation.
- **Open Questions block phases when load-bearing.** Q1 (`VibeFlow` failure semantics) is not a tunable; it is a precondition for P3. Settle, then ship.

## Issues With The Current Plan

### 0. Missing: north-star API section

Before architecture, layer definitions, and rollout, the plan should show the *desired user experience* — three or four worked examples covering a single-graph template, a multi-stage `VibeFlow`, a custom-node use, and an escape hatch. Without this anchor, every downstream design decision is judged in the abstract. A reader (or reviewer) cannot tell whether `wf.node(...).out("image")` actually feels right until they see five lines of an end-to-end recipe. This is a structural gap, not a wording issue: the plan currently leads with the architecture diagram (`python_composition_dsl_plan.md:48`) and only shows isolated snippets later. Add the north-star section first, then judge every abstraction against whether it pulls its weight in those examples.

### 1. Abstraction sprawl

Template, Pipeline, Recipe, VibeFlow, and `build()` are too many names for one container axis. The collapse is straightforward:

- **Template** keeps its place as the reusable single-graph builder shape — the Flux 4B native builder is the precedent (`ready_templates/image/flux2_klein_4b_t2i.py:81`), and Template earns its own term by exposing default requirements, metadata, and override points.
- **VibeFlow** keeps its place as the multi-stage orchestration container.
- **Recipe** should be dropped. It is parenthetical at the heading (`python_composition_dsl_plan.md:90`), never appears as a type, but pollutes the provenance schema with a `"recipe"` key (`python_composition_dsl_plan.md:271`). Pick Template or VibeFlow; nothing is gained by a third synonym.
- **Pipeline** as currently described overlaps with both Template (single-graph case) and VibeFlow (multi-stage case). Either fold it into one of those, or give it a non-overlapping job (e.g., async/streaming variant) and say so.

**Block vs Patch** is more nuanced. The signatures are identical today (`(workflow, **kwargs) -> Handles` per `vibecomfy/blocks/__init__.py:38-40`), but the *intents* are genuinely different: blocks construct nodes and return handles; patches decorate or splice existing topology. The plan should pick one of two paths: (a) enforce the distinction via API shape — e.g., Patch as `(workflow) -> None` or `(workflow) -> workflow`, no handle return — so the type system reflects the conceptual split; or (b) explicitly state that Patch is a behavioral convention over Block, with a `@patch` decorator that records intent in provenance even though the contract is identical. The current "two names, identical signatures, intent-only difference" is the worst of both options because authors will not know which to write.

### 2. `Handle[T]` static-typing claim is overstated

`Handle[T]` carries real value at runtime — introspection, lint surface, doctor checks, error messages, and debugging UX all benefit from a typed wrapper over `(node_id, slot)`. That is worth keeping. The problem is the plan implies *static* type safety that Python cannot deliver as designed.

`wf.node(class_type: str, **kwargs)` cannot propagate `T` to the returned handle without one of:

- `@overload` per known class_type with `Literal`-discriminated `.out(name)` returns; or
- generated typed wrapper functions (`wf.vae_decode(...)`).

Neither is committed in any phase. As written, every `Handle` is `Handle[Any]`, so `wf.node("SaveAudio", images=image_handle)` type-checks even though it is wrong. The plan calls this "typed" at SD-010 and lines 282-288 in a way that reads as mypy-grade safety; it should instead say P1 delivers **typed metadata and lintable handles**, with full static checking deferred to whichever later phase commits to overloads or codegen.

The schema-string→Python-type registry that P4 depends on is also undefined. `OutputSpec.type` (`vibecomfy/schema/provider.py:26-29`) is `str | None` carrying values like `"IMAGE"`, `"LATENT"`, `"WANVIDEOMODEL"` — there is no documented mapping to Python type symbols, no fallback policy for unmapped types, and no decision about the long tail of 1,202 node classes (`docs/runtime/surface.md:36`).

### 3. `str(handle)` coercion is a silent type-erasure path

`VibeWorkflow.connect` at `vibecomfy/workflow.py:128-132` parses `from_ref.split(".", 1)`, and `Handles.values` at `vibecomfy/blocks/__init__.py:13` is `Mapping[str, Any]`. So any handle that touches `connect()`, dict lookups, f-strings, or equality silently degrades to a string with no warning. The proposed `untyped_raw_ref` lint catches the *source* side but not the *coercion* side.

### 4. The "no arbitrary Python in active graph" rule has no enforcement

SD-005 is documented as a hard rule, but `Block` is a Protocol with no validator, and `compile("api")` does not check that `node.inputs` and `node.widgets` values are JSON-serializable before they hit the API dict at `vibecomfy/workflow.py:185`. Nothing rejects a block that closes over live Python state and stuffs an opaque object into an input.

### 5. `VibeFlow` executor is critically under-specified for P3

Open Question #1 (failure-mode semantics) is treated as a tunable, but the answers determine whether P3 is shippable:

- **Cancellation:** `await self._comfy.queue_prompt_api(api_dict)` (`vibecomfy/runtime/session.py:144`) is not shielded; a `CancelledError` mid-stage leaves HiddenSwitch executing.
- **Parallelism:** `EmbeddedSession` holds a single `_comfy` context (`vibecomfy/runtime/session.py:92-93`). Two stages cannot run concurrently against one session, and the doc never says so.
- **Run-dir collisions:** each stage gets its own `run-<int(time.time())>` dir (`vibecomfy/runtime/session.py:127`); same-second stages collide.
- **Flow identity:** nothing in `RunResult` ties a stage back to its position in a `VibeFlow`, so resume/idempotency is impossible.

### 6. Custom-node lifecycle has races and no real reload verb

- `EmbeddedSession.stop()` (`vibecomfy/runtime/session.py:185-195`) does not check that no `run()` is in flight; a concurrent stop tears down `_comfy` while `queue_prompt_api` is still awaiting.
- `ServerSession.reconfigure` (`vibecomfy/runtime/session.py:281-290`) only reacts to argv changes. A nodepack install does not change argv, so reconfigure will not pick it up. There is no `session.reload_for_nodepack_change()`.
- External-server mode has no detection path, no error class for "restart required," and no UX for the human to acknowledge.

### 7. SHA verification is documented but not implemented

`custom_nodes.lock` records `(name, sha, url)` but nothing in `vibecomfy/runtime/session.py` reads it before `start()`. `_run_metadata` (`vibecomfy/runtime/session.py:487-507`) records the *vibecomfy* repo's `git_sha`, not custom-node SHAs. `source_sha256` is doc-only — no compute, no store, no compare. Mismatch policy (warn / fail-closed / auto-reinstall) is undefined.

### 8. Escape hatches are a one-way door

`VibeFlow` stages are `VibeWorkflow | Callable -> StageResult`. A user with a raw API dict has neither, and there is no `VibeWorkflow.from_api_dict()` — only `convert_to_vibe_format` for ready templates (`vibecomfy/registry/ready_template.py:19`). Escape-hatch users cannot feed raw-dict results into a downstream Python stage with typed `Handle`/`Artifact` semantics.

### 9. The "native builder" precedent contradicts the proposed API

`ready_templates/image/flux2_klein_4b_t2i.py` is the migration model (`python_composition_dsl_plan.md:241`), but it defines its own private `node()` helper at line 172, bypasses `wf.node().out()`, and uses raw string `connect("12.0", "13.text")`. Either the precedent needs rewriting against the proposed API, or hand-IDs + string refs are the real authoring surface and `wf.node().out()` is sugar no one will use.

### 10. `run_until` API contract during P1–P3 is undefined

The doc says the debug runner is "unavailable" until P4 but never says *how*: missing attribute, `NotImplementedError`, conditional raise on `output_type is None`, or partial behavior for hand-populated `output_type`. Downstream code will form against partial behavior and break at the cutover.

## Recommendations

### Edits to the plan doc

1. **Add a north-star API section before the architecture diagram.** Three to four worked examples: single-graph template, multi-stage `VibeFlow`, custom-node use, escape hatch. Every later abstraction is judged against whether it earns its keep in those examples.
2. **Collapse terminology.** Keep `Template` for reusable single-graph builders. Keep `VibeFlow` for multi-stage orchestration. Drop "Recipe." Decide whether `Pipeline` is a synonym (drop it) or a non-overlapping variant (define what makes it different).
3. **Pick a stance on Block vs Patch.** Either differentiate by signature (Patch returns no handles) or explicitly mark Patch as a behavioral convention with a `@patch` decorator that records intent. Do not leave it as identical signatures with intent-only differences.
4. **Tighten `Handles` to `Mapping[str, Handle]`** and unify Stage/Run results around `Handle | Artifact` so the cross-stage value type is consistent.
5. **Reframe the `Handle[T]` claim.** Say P1 delivers typed metadata and lintable handles. Defer mypy-grade static safety to whichever later phase commits to overloads or codegen, and publish the `SCHEMA_TYPE_REGISTRY: dict[str, type]` that ungates it.
6. **Promote Open Question #1 to a Settled Decision before P3.** Specify cancellation propagation, single-session serialization, flow-scoped run-dir naming, and resume identity.
7. **Define the `run_until` contract during P1–P3** — recommend "raises `NotImplementedError` until `handle.output_type is not None`," so the cutover is invisible.
8. **Stop describing `ExternalPythonNode` in present tense.** It is aspirational until P3 codegen lands; mark it as such.
9. **Rewrite the Flux 4B builder against the proposed API** before declaring it the migration model — or admit hand-IDs + string `connect()` are the real surface and demote `wf.node().out()` to optional sugar. The current builder is a *transition* precedent, not the final shape.

### Code-level gates that must accompany the doc

These convert documented rules into enforced invariants. Tiered by phase:

**P1 hard gates** (cheap, prevent foot-guns from forming against partial behavior):

- **`Handles -> Mapping[str, Handle]`** tightening so the block return shape is consistent from day one.
- **`run_until` raise contract** — `NotImplementedError` until `handle.output_type is not None`. Documented now so downstream code never forms against partial behavior.
- **Lint/doctor coverage of `str(handle)` coercion sites** — at minimum a warning when raw string refs are used where a typed `Handle` is in scope, and when `str(handle)` flows into `connect()` or dict keys. Backward compat stays; the silent erasure stops being silent.

**P1/P2 hardening** (lands as the API surface stabilizes):

- **Typed `wf.connect(handle_a, handle_b)` overload** that never routes through `split(".")`, plus `Handle.__eq__` matching the string form so both sides interoperate without manual `str()`.
- **Compile-time serialization gate** in `compile("api")`: every `node.inputs`/`node.widgets` value must be JSON-serializable or a recognized edge ref `[node_id, slot]`. Only `ExternalPythonNode` may set an opt-out sentinel. Enforces SD-005. Lands no later than the first block library expansion that introduces non-trivial Python in builders.

**P3 pre-reqs** (must land before `VibeFlow` ships):

- **Open Question #1 settled** as Settled Decision: cancellation, serialization, run-dir naming, resume identity.
- **In-flight guard on `session.stop()`** — refuse, or cancel-and-await — so concurrent stop/run does not tear down `_comfy` mid-prompt.
- **`session.reload_for_nodepack_change()`** as an explicit verb. The documented `stop()/install/start()` recipe is not a contract; the reload needs its own named operation.
- **`VibeWorkflow.wrap_api_dict(d)`** so raw-dict workflows can be a `VibeFlow` stage. Closes the escape-hatch one-way door.

**P4 pre-req:**

- **Schema-string-to-Python-type registry** published with a documented fallback for unmapped types. Without it, `run_until` cannot ungate.

**Lockfile hardening (timing flexible, but blocks calling `vibecomfy nodes lock` "done"):**

- **`vibecomfy doctor` SHA verification verb** with a defined mismatch policy (recommend fail-closed by default with explicit `--allow-drift` opt-in). Without this, the lockfile is decoration.

### Open questions worth keeping

- ExternalPythonNode subprocess vs in-process module (Q4) — genuine tunable, defer.
- `MarkdownNote` strip vs preserve (Q3) — genuine tunable, defer.
- Whether `Handle` carries `block_id`/recipe context directly or only via composition trace (Q2) — defer; provenance trace is sufficient for P1.

## Bottom Line

The plan is conceptually coherent and the layering instinct is right. The gap is between the prose and the code: several load-bearing claims (typed handles, no-Python-in-graph, session reload, SHA pinning, escape-hatch interop) exist only as documentation today. P1 is buildable as-stated, but P3 is not until Open Question #1 is settled and the runtime gates above are in place. Address the eleven issues above, land the tiered enforcement gates (3 in P1, 2 in P1/P2, 4 before P3, 1 before P4, plus the lockfile verb), and the plan becomes sound to build on.
