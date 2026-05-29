# Interrogation — Composition Ergonomics / Developer Experience

**Lens:** When an EXTERNAL builder sits down to compose Arnold's pieces (dispatch / state / emit /
evidence / config + drivers + node library + package contract) into a NEW, non-planning tool, where
does it get painful? The SDK's entire value is composability; if the DX is bad the SDK fails even if
the pieces are "right." This memo assumes the FULL ambition ships (EPIC + m1–m6); it names what the
plan must ADD — scaffolding, types, inspector, docs — to clear the DX cliffs. No scope reduction.

**Verdict in one line:** the EPIC has exhaustively designed the *pieces* and zero of the *composition
surface*. The hardest unsolved problem in this epic is not de-planning the types (m2) or building the
loop driver (m3) — it is that **a composed pipeline has no static, build-time, or discovery-time safety
net of any kind**, and the failure modes a fourth builder will actually hit (silent discovery drop,
runtime `LookupError` on a `next`/edge typo, "step 4 got garbage" with no trace) are exactly the modes
the plan never mentions. The acceptance tests (m2 tournament, m3 solver, m6 fourth tool) are all written
*by people who already know the SDK*, so they will pass while a real external builder bounces off.

---

## BITE 1 (CRITICAL) — Discovery silently swallows every authoring error

**Where:** `megaplan/_pipeline/registry.py:301` `_load_module_from_path` →
`except Exception: ... return None` (out-of-tree user packages), and `except ImportError: return None`
(in-tree). `discover_python_pipelines` (`registry.py:360`) further drops any module lacking a callable
`build_pipeline` "silently" (its own docstring, `registry.py:368`). M6 then makes **`SKILL.md` a
required package element** ("fail discovery loud if absent", m6 scope item 1 / m6 §67) — adding a *new*
reject path to a discovery layer that currently rejects *everything* in silence.

**Why it bites:** This is the very first thing a fourth builder does — drop a package in
`~/.megaplan/pipelines/` and run `megaplan list`. If they have a typo in `from megaplan._pipeline...`,
a syntax error, a missing dep, a `build_pipeline` they spelled `build_pipline`, or (post-M6) a missing
`SKILL.md`, their package **does not appear and they get no error, no warning, no log line**. The
`except Exception` is annotated `# noqa: BLE001 — discovery is best-effort` — "best-effort" is the
correct posture for *megaplan's own* discovery, but it is the single most hostile possible posture for
a *builder SDK whose entire pitch is "drop a package and it's first-class."* The builder cannot tell
"my package isn't being scanned" from "my package crashed on import" from "I named the entrypoint
wrong." Acceptance test #1 (the fourth tool) will be written by someone who reads the source and gets
the entrypoint name right on the first try — so it passes and this cliff stays invisible until the
first real external user.

**Severity:** CRITICAL. The contract `manifest + driver + bindings + SKILL.md → discovered like
jokes/doc` (EPIC:37,48) is the SDK's headline promise, and the discovery path actively hides why the
promise didn't fire.

**What it forces the plan to ADD:** A diagnostic discovery mode. `discover_python_pipelines` must
collect `(name, error)` for every module it rejected and expose them; M6 must ship a
`megaplan pipelines doctor` / `--explain-discovery` that prints, per scanned path: discovered ✓ /
rejected (with the actual traceback) / skipped (collision with built-in). The `except Exception`
must re-raise (or record) under that mode. Without this, "discovered identically to jokes/doc" is a
trap — jokes/doc are in-tree and never fail discovery, so the in-tree apps never exercise the
silent-drop path the external builder lives in.

---

## BITE 2 (CRITICAL) — `next`/edge wiring has no static or build-time check; it fails as a runtime LookupError mid-run

**Where:** A Step hand-writes its routing string (`StepResult(next="critique")`, `doc/steps.py:80`,
`:25`, `:110`), and the package author *separately* hand-writes the graph edges in `build_pipeline`
(`Edge(label="critique", target="critique")`, `doc/__init__.py:90-105`). Nothing checks the two
agree. The ONLY enforcement is the executor raising `LookupError` **when that stage actually runs**
(`executor.py:299`, `:401`: "Stage X produced next=Y" with no matching edge). `NextEdge = str`
(`types.py:74`) — it is a bare string, no `Literal`, no enum, no per-pipeline type.

**Why it bites:** This is the textbook "type mismatch between one piece's output and the next's input
with no static help" failure the lens is about — and it's worse than a type mismatch because it's a
*string* mismatch with no type at all. Three concrete traps a fourth builder hits:
(1) `doc/steps.py` itself ships **two different naming conventions in one pipeline** —
`OutlineArtifactReader.run` returns `next="done"` (`steps.py:45,52`) while every Stage edge uses the
stage's name (`next="critique"`). The canonical worked example a builder learns from is internally
inconsistent about what a `next` string even means (stage name? "done"? "halt"?).
(2) `'halt'` is a reserved magic string a Step must return *directly* and which must NOT appear as an
edge label — the doc pipeline's `AssemblyStep` returns `next="halt"` and the module docstring has to
*warn* that "a halt-labelled edge would be unreachable" (`doc/__init__.py:19-21`). A builder who adds
a halt edge gets a silently dead stage.
(3) Rename a stage in `build_pipeline` and forget the matching `next=` in `steps.py` → no error until
that branch executes, possibly only on the unhappy path (a gate's `iterate` edge), possibly only after
several minutes and dollars of LLM dispatch. M3 makes this strictly worse: it adds *gate-consequence*
routing (`advance|revise_in_place|restore_and_diverge|escalate`, m3 scope) so now there are TWO
parallel dispatch keys (`Edge.label`==`next` AND `Edge.recommendation`==`verdict.recommendation`,
`types.py:87-96`) and a builder can mis-wire either.

**Severity:** CRITICAL. Composability *is* wiring outputs to inputs; this is the join the SDK exists to
make safe, and today it's unityped strings checked at runtime.

**What it forces the plan to ADD:** A `Pipeline.validate()` / graph linter that runs at `build_pipeline`
time (and in discovery, and as `megaplan pipelines check <name>`) asserting: every Stage's reachable
`next` labels (statically declarable on the Step, or at minimum every `Edge.label`) resolves to an
edge; every `Edge.target` resolves to a stage or `'halt'`; no stage is unreachable from `entry`; no
`'halt'` edge label; for gate stages, the verdict labels the binding supplies have matching gate
edges. This is a few hundred lines and it is THE thing that converts "manifest + driver + bindings"
from a runtime-roulette into a real SDK. It belongs in M1 (foundation/hygiene) or M2, not deferred —
every later milestone adds more edges to mis-wire. Steps should also be able to *declare* their
possible `next` labels (a `out_labels: tuple[str,...]` attribute) so the linter is exact, not a
best-effort scan.

---

## BITE 3 (HIGH) — No execution trace from the executor: "step 4 got garbage" is undebuggable

**Where:** `executor.py` emits **no trace events of its own** — there is no per-step "entered stage X /
Step returned next=Y / matched edge kind=gate rec=iterate / advancing to Z" record anywhere in the
run loop (grep of `executor.py` for emit/event/log returns only comments and the escalate-policy
branch). `emit` is a separate piece (`EventSink.emit`, EPIC:33) wired by *callers/handlers*, not the
executor. So the dispatch decisions — the exact thing you need when a composed pipeline misbehaves —
are invisible unless every Step author remembers to emit them, by hand, consistently.

**Why it bites:** The lens question "where do you look when step 4 gets garbage?" has no answer in this
SDK. A planning author has handlers that happen to log; a *fourth builder* composing raw Steps gets a
black box: input went in, wrong output came out, and the routing/state-patch decisions in between left
no record. m3's loop driver and m5's `fan_out` make this acute — a data-predicate loop that runs the
wrong number of times, or a fan-out where one of N shards returns garbage and the `reduce` quietly
absorbs it, is nearly impossible to diagnose without a built-in trace of `{iteration, predicate
value, budget, per-shard result}`. The EPIC's own observability doc exists for *planning* phases; the
SDK executor has no equivalent for arbitrary compositions.

**Severity:** HIGH. Debuggability of a composition is a first-order DX property; without it the SDK is
only usable by people who can read its source.

**What it forces the plan to ADD:** The executor must emit a structured trace through the `emit` piece
*by default* — one event per stage entry/exit carrying `(stage, step.kind, next, matched_edge,
state_patch_keys, verdict)`, and for the m3 loop driver one event per iteration carrying
`(iteration, predicate_result, budget_remaining)`, and for m5 `fan_out` one event per shard. Plus an
offline replay/inspect tool (`megaplan pipelines trace <plan_dir>`) that renders the path taken. This
should be a named deliverable in M3/M4 (where `emit` and the drivers land), not left to each binding.

---

## BITE 4 (HIGH) — The fluent `Pipeline.builder()` and the raw `Stage`/`Edge` form are two unreconciled authoring surfaces, and the worked examples teach the raw one

**Where:** `types.py:244` ships `Pipeline.builder(...)` → `PipelineBuilder` (a fluent constructor with
`worker`/`prompt_registry`/`pipeline_version` knobs). But every actually-shipped package
(`doc/__init__.py:66`, and per the briefs `creative`, `epic-blitz`) ignores it and hand-builds a raw
`dict[str, Stage]` with `Edge(...)` tuples. Prompt registration is a separate **import-side-effect**
ritual (`from ...doc import prompts as _prompts  # noqa: F401`, `doc/__init__.py:49`) that a builder
must know to perform or their `prompt_key`s resolve to nothing. M6 declares `build_pipeline()` the
entrypoint and the node library (m5 F9) the "public composition vocabulary" — but never reconciles
which of the two authoring surfaces is *the* one, nor folds prompt registration into it.

**Why it bites:** A fourth builder reading the codebase finds two ways to build a pipeline, a fluent
API that nothing uses, and a load-bearing `# noqa: F401` import they'll omit (and then debug a "prompt
not found" with no hint it was a missing import). The learning curve is "read the source of doc, copy
it, and hope you copied the rituals." That is the gap between "manifest + driver + bindings" and a
working pipeline the lens warns about — it's currently bridged by source-reading, not by a contract.

**Severity:** HIGH.

**What it forces the plan to ADD:** M6 must pick ONE blessed authoring surface and make the node-library
macros (m5 F1 `critique_revise_gate_loop`, F2 `fan_out`/`panel`) return *wired* sub-graphs so a builder
composes macros, not raw `Edge` tuples (the way `dynamic_fanout` already hides its wiring in
`doc/__init__.py:79`). Prompt registration must be declarative on the package manifest, not an import
side-effect. And there must be a `megaplan pipelines new <name>` scaffold that emits a minimal,
*valid, discovery-passing* package (manifest + `build_pipeline` + one Step + `SKILL.md` stub) so a
builder starts from green instead of from a blank file and the silent-drop cliff (BITE 1).

---

## Single biggest MISSING ABSTRACTION

**A package/composition "contract checker" — the build-time validation + diagnostic-discovery + scaffold
surface — is entirely absent from the plan.** The EPIC defines the package *contract* as "manifest +
driver + bindings + SKILL.md" (EPIC:37) but ships no tool that *verifies a package satisfies the
contract* before (or instead of) crashing at runtime. Today the only checks are runtime: `LookupError`
on bad routing (`executor.py:299`), `FileNotFoundError` on a missing declared output (`executor.py:140`),
and silent `None` on a bad import (`registry.py:301`). For an SDK whose value is composition, the
missing piece is a `validate(pipeline) -> Diagnostics` / `megaplan pipelines check` that statically
proves a composition is wired, discoverable, and contract-complete — the equivalent of a type-checker
for the graph. Every BITE above is a facet of this one hole. It should be an explicit M1/M2 deliverable
with the acceptance test "feed it a deliberately mis-wired package and assert it names the exact
defect" — the mirror image of the fourth-tool happy-path test.

## Single biggest OVER-COMPLICATION

**The dual dispatch keys on edges** (`Edge.label`+`StepResult.next` for `kind="normal"` vs
`Edge.recommendation`+`verdict.recommendation` for `kind="gate"`, `types.py:78-96`), now compounded by
m3's separate gate-*consequence* map (`advance|revise_in_place|restore_and_diverge|escalate`). A fourth
builder must hold three routing concepts — a label string, a verdict recommendation, and a consequence
— to wire one gate, and the executor matches them in a priority order (`executor.py:281-299`) that's
documented only in prose. m2/m3 correctly *decouple* verdict-label from consequence, but they bolt the
consequence on as a third axis rather than collapsing routing to one model. The plan should, while it
has the types open in m2/m3, unify dispatch to a single "Step emits a routing key; the gate-consequence
binding maps key→consequence; edges are declared by key" model so a builder learns ONE routing concept,
not three layered ones. (Not scope reduction — it's the same capability behind one mental model.)

## Single biggest OVER-SIMPLIFICATION

**`NextEdge = str` (`types.py:74`) and `outputs: Mapping[str, Path]` (`types.py:161`) as the entire
inter-step interface.** The plan's whole abstraction-correctness effort (m2) is about getting the
*aggregate/verdict* types right (`ReduceResult`, `SelectionResult`, `Reduce[T]`) — genuinely good work —
but it leaves the *most-used* inter-step contract, the routing string and the output-label→path map,
as untyped stringly-typed dicts with zero compile-time help. A builder wiring step→step gets a
`SelectionResult` that's nicely typed and a `next`/`outputs` handshake that's a bag of strings. The
plan over-trusts that "the verbs are at the right altitude, fix the types" means fixing the *aggregate*
types; the inter-step *plumbing* types are where a fourth builder spends 80% of their wiring time and
they get no help. m2 should additionally give Steps a declared output-schema and routing-label set so
the linter (missing abstraction, above) can check the handshake — otherwise the de-planning-ized types
are a beautifully typed island in a sea of `str`.
