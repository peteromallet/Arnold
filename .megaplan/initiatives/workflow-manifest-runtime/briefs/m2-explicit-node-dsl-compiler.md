# M2: Explicit-Node DSL And Compiler

## Outcome

Implement the canonical `arnold.workflow` authoring surface and `arnold.patterns` constructors so explicit Python data pipelines compile to the M1 `WorkflowManifest` contract with stable IDs, refs, source spans, validation, inspection, and dry-run output.

The reviewer should be able to build a minimal Megaplan-shaped explicit-node pipeline, compile it to a serializable manifest, inspect it as YAML/DOT/dry-run data, and see compile-time rejection of non-durable Python identities.

## Operating Philosophy

M2 makes authoring pleasant without weakening durability. Helpers may improve ergonomics, but the compiler must force all topology, refs, callouts, and control routes into stable manifest data before runtime. Anything that depends on live Python identity, hidden control flow, or product policy belongs outside the public authoring contract.

## Scope

IN:

- Create `arnold/workflow/__init__.py`, `dsl.py`, `refs.py`, `compiler.py`, `validation.py`, `inspect.py`, `dry_run.py`, `expressions.py`, and internal lowering IR as needed.
- Create `arnold/patterns` constructors for `agent`, `branch`, `critique`, `fanout`, `human_gate`, `loop`, `merge`, `panel`, `retry`, `review`, `revise`, `subpipeline`, `tournament`, and `external_call` as pure serializable/lowerable values.
- Support canonical `workflow.Pipeline(id=..., version=..., steps=[...])` with explicit stable node IDs.
- Resolve `decide=`, `until=`, reducers, prompt builders, policies, and pattern factories to importable `module:qualname` identities.
- Reject closures, lambdas, bound methods, callable objects, live instances, arbitrary runtime Python control flow over refs, and hidden object-identity dataflow.
- Lower branch, loop, fanout, retry, `human_gate` pattern, and subpipeline shapes to manifest scopes and `reentry_id`s. The `human_gate` pattern lowers to generic suspension/capability routes, not a human-specific kernel primitive.
- Add inspect/dry-run output for nodes, refs, dependencies, capabilities, possible routes, and unresolved inputs.
- Add compile-time purity tests proving `arnold.patterns` and DSL constructors produce only manifest-compatible pure data: no closures, lambdas, bound methods, callable instances, mutable live instances, or hidden object-identity dataflow.
- Add authoring-error conformance: every compile-time rejection should name the offending node or field, explain the violation, and provide a concrete remediation.
- Define the explicit-node package authoring contract: package-level `build_pipeline()`, required metadata, pipeline ID registration, SKILL.md expectations, discovery metadata, and how package manifests relate to compiler-produced `WorkflowManifest` output.
- Lock the package authoring signature and accepted return type: `build_pipeline()` returns `workflow.Pipeline` only. `WorkflowManifest` is compiler output, not hand-authored package source. Any old `NativeProgram`, builder, executor, or `_forward_m2_m3` graph object is quarry only unless absorbed into the new schema and deleted from the old location.
- Document which inspect/dry-run/source-span fields are stable public tooling fields versus diagnostic-only fields.
- Add explicit public/provisional/internal markers for exported `arnold.workflow` and `arnold.patterns` symbols.
- Add a pattern stability matrix declaring each `arnold.patterns` constructor stable, provisional, or internal. Public patterns may be broad, but they must emit no product literals, hidden product defaults, or runtime-only objects.
- Add a named canonical Megaplan-shaped manifest fixture matrix, `tests/fixtures/workflow/canonical_megaplan_manifest.*` or equivalent, covering branch, loop/revise, fanout/panel, retry/tiebreaker, subpipeline, generic suspension/human capability, override edges, fallback edges, escalation targets, compensation targets, supervisor-promotion routes, feedback-phase topology, robustness variants, and dynamic-topology overlay event slots. M3 must consume this exact fixture matrix.
- If the compiler discovers a missing manifest invariant, update M1 contract tests and `workflow-manifest-amendments.md`; do not silently widen manifest shape.

OUT:

- No real execution runner; use compile/inspect/dry-run only.
- No package move to `arnold_pipelines.megaplan`.
- No public restricted-Python generator syntax.
- No fluent builder as canonical docs or scaffolding.

## Locked Decisions

- Canonical authoring is explicit-node data: `workflow.Pipeline(..., steps=[...])`.
- Helpers may standardize defaults but must return pure Arnold step values and may not hide topology, side effects, budgets, or dynamic routes.
- Constructor surfaces compile to manifests. No DSL, pattern, builder, or constructor object may cross the compile boundary into execution.
- Runtime branching uses `branch`, `loop`, `fanout`, `retry`, `subpipeline`, and `human_gate`, not Python `if`/`while` over runtime refs.
- YAML/JSON is generated interchange/manifest output, not hand-authored source.
- Restricted Python remains private/future sugar over the same manifest.
- Generic hook resolution and prompt-builder references are part of `arnold.workflow`; Megaplan-specific prompt-builder patterns belong in `arnold_pipelines.megaplan`.

## Resolved Execution Decisions

- Typed refs and fallback refs expose stable node/output identities, dependency metadata, and fallback routing metadata only; they do not expose live values or Python control-flow hooks.
- Prompt, policy, reducer, and condition references are authored as durable refs validated by the compiler and resolved through startup registries at runtime. M2 may validate `module:qualname` syntax and importability for author feedback, but M3 never imports product code from manifest fields.
- Source spans must identify the user-authored node/pattern call and enough helper expansion context to make compiler errors actionable. Generated helper internals can be diagnostic-only unless locked in inspect/dry-run public fields.
- Stable inspect/dry-run fields are node IDs, refs, dependency graph, capability/control routes, suspension points, manifest hash inputs, and topology summary. Formatting, source-span detail, and explanatory text remain diagnostic.
- Public pattern constructors in M2 are stable only when they emit product-neutral manifest shapes and pass the fixture matrix; unproven constructors are marked provisional and must be promoted or kept internal before M5 docs/scaffolds expose them.
- `_forward_m2_m3.py` is quarry only. Any useful routing, port, graph, or scope concepts become explicit `arnold.workflow`/manifest/kernel contracts; the old file and old graph objects are deletion targets.

## Constraints

- The compiler must not execute arbitrary workflow author code to discover runtime topology.
- Manifest output must be deterministic across processes.
- Public docs/examples in this sprint should teach only explicit-node authoring.
- Do not widen M1 manifest fields casually; if the compiler needs a new field, update contract tests and docs.
- `arnold.execution` must not be introduced as a dependency of `arnold.workflow` or `arnold.patterns` compile-only tests.
- The compiler must not widen manifests to accommodate product-owned control target types.

## Done Criteria

1. Explicit-node DSL constructors exist and compile to `WorkflowManifest` v1.
2. Pattern lowering tests cover branch, loop, fanout, retry, `human_gate` lowering to generic suspension/capability routes, subpipeline, merge, and external call.
3. Importable-hook validation accepts named functions and rejects non-durable callables.
4. Inspect/dry-run tests show stable routes, refs, capabilities, source spans, and topology hash behavior.
5. A canonical Megaplan-shaped compile-only test proves the target authoring style works.
6. A separate-process serialize/deserialize compile test proves a patterns-built pipeline does not depend on live Python object identity.
7. Public/provisional/internal symbol markers and explicit `__all__` lists exist for `arnold.workflow` and `arnold.patterns`.
8. Authoring-error tests cover invalid callable identity, invalid refs, hidden topology, bad hook strings, and unsupported runtime control flow.
9. The named canonical Megaplan-shaped fixture matrix exists and validates against the compiler without requiring runtime execution.
10. The canonical fixture matrix includes at least two full tiebreaker rounds and validates recursive loop-back behavior instead of flattening tiebreaker into a one-shot subpipeline.
11. Each canonical fixture variant produces a stable manifest hash across processes and passes a semantic manifest-diff check against locked expected node/ref/capability/suspension/control shapes.
12. Docs or examples added in this sprint avoid `PipelineBuilder`, `Stage`, `Edge`, native decorators, and fluent chaining as canonical style.

## Touchpoints

- `arnold/workflow/`
- `arnold/patterns/`
- `tests/arnold/workflow/`
- `tests/arnold/workflow/test_canonical_megaplan_conformance.py`
- `docs/arnold/workflow-authoring.md`
- `docs/arnold/workflow-manifest.md`
- `docs/arnold/package-authoring-contract.md`
- package discovery metadata and pipeline ID registry artifacts
- legacy `_forward_m2_m3.py` graph/port/routing concepts as quarry-only source material

## Anti-Scope

- Do not add a second public manifest syntax.
- Do not execute live Python object graphs as a shortcut.
- Do not expose native generator decorators as public workflow authoring.
- Do not move Megaplan product files yet.
- Do not import `arnold.execution` to make compiler tests pass.

## Suggested Run

`partnered-5/thorough/high`

This sprint defines a public authoring and compiler contract that downstream product packages and docs will build on; bad choices here can pass tests while locking in a weak API.
