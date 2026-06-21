# Workflow Manifest Runtime Review: Initial Analysis

Date: 2026-06-21
Source objective: `/Users/peteromalley/Documents/megaplan/plan.md`
Plan artifacts under review: `.megaplan/briefs/workflow-manifest-runtime/`

## Ten End-State Expectations

1. The repo has a clean separation between neutral Arnold workflow/kernel/runtime packages and the Megaplan product package. Neutral Arnold code must not import Megaplan product code.
2. The canonical authoring model is an explicit-node Python data DSL that compiles to a durable `WorkflowManifest` contract. Execution runs manifests, not live Python object graphs, generator frames, or compatibility wrappers.
3. The manifest schema is deterministic and complete enough for real workflows: nodes, refs, edges, source spans, policies, budgets, retry, loops, fanout/fanin, subpipelines, human gates, reentry IDs, topology hashes, and manifest hashes.
4. The runtime owns policy-blind execution semantics: append-only journals/events, artifact hash binding, capability/effect enforcement, resume cursors, replay, fake backends, branch routing, loop control, retry, fanout/fanin, subpipeline execution, and human suspension/resumption.
5. Megaplan one becomes a product pipeline under the new product package, built as explicit workflow data over the manifest runner. Its prep, plan, critique/review, gate, revise loop, tiebreaker, human gate, finalize, execute, post-review, status, trace, and resume behavior must match current behavior through goldens/parity.
6. Shipped/example pipelines move to the same public authoring/runtime surface instead of keeping separate legacy/private pipeline systems.
7. CLI, docs, templates, package metadata, and generated skills present only the new public surface once the cutover is complete.
8. Legacy surfaces are deleted rather than kept as permanent compatibility shims: top-level `megaplan`, `arnold.pipelines.megaplan`, `_pipeline`, bridge modules, native runner/hooks, and obsolete public builders/import paths.
9. Conformance is stronger than import greps alone: installed-wheel smoke tests, import graph checks, docs/scaffold checks, manifest/golden parity, replay/resume checks, behavior goldens, and deletion gates prove the clean break.
10. The work is sequenced so contracts and parity gates land before churn: baseline/manifest, DSL/compiler, runner/runtime, Megaplan migration, shipped pipelines/docs, then purge/conformance.

## Ten Surface Edges To Audit

1. Public import surface: `arnold.workflow`, `arnold.patterns`, `arnold.execution`, `arnold.kernel`, `arnold.agent`, future `arnold_pipelines.megaplan`, old `megaplan`, and old `arnold.pipelines.megaplan`.
2. CLI surface: current `megaplan`/Arnold commands, workflow inspect/dry-run/run/status/trace/resume controls, generated parser snapshots, and installed console entrypoints.
3. Authoring surface: DSL constructors, pattern helpers, explicit node identity, source spans, callable hook references, prompt builders, scaffolds, templates, generated docs, and skill instructions.
4. Runtime semantics: branch decisions, retries, loops, fanout/fanin, reducers, subpipelines, human gates, suspend/resume, cancellation, and reentry.
5. State/artifact surface: plan repository, state deltas/CAS, capsules, artifact adapters, receipt schema, taint/provenance, content types, and durable artifact hashes.
6. Agent/tool/model dispatch surface: model routing, budget authority, key pool, workers, sandboxing, tool effects, approvals, browser/terminal/MCP/openrouter/session/vision tools.
7. Observability/control surface: events, execution evidence, cost tracking, status projection, control interface, overrides, feedback, gates, governor, and supervisor state.
8. Discovery/package surface: pipeline registries, package authoring contracts, pipeline IDs, package manifests, discovery trust gates, docs generation, and py.typed/type-check promises.
9. Test/golden surface: behavioral goldens, characterization corpus, oracle tests, conformance allowlists, parser snapshots, installed-wheel tests, and no-golden-update rules.
10. Migration/deletion surface: module relocation inventories, temporary aliases, M6 deletion gates, docs migration guidance, external consumer assumptions, and old path failure tests.

## Initial Technical Sequencing Anchor Points

1. Do not start from the dirty `native-python-pipelines` checkout. Branch from `origin/main`; use dirty work only as quarry.
2. Freeze behavior before moving packages. Behavior fixtures must normalize volatile fields and block import-only moves from rewriting goldens.
3. Define the manifest and kernel contracts before exposing authoring helpers. Later stages should not discover missing event/ref/hash semantics ad hoc.
4. Build the DSL/compiler before the runner. Dry-run/inspect/source-span validation should catch bad workflow shape without invoking execution.
5. Build the runner against manifests before migrating Megaplan. Product migration should not define runtime semantics by accident.
6. Migrate Megaplan before examples/docs. The canonical product flow is the hardest proof that the substrate works.
7. Move examples, templates, CLI, and docs only after the product path is stable, so public-facing guidance does not churn twice.
8. Delete old public surfaces only after installed-wheel and parity gates pass. The purge milestone should be mostly mechanical plus conformance.
9. Keep policy vocabulary product-owned. Generic runtime should route string decisions/capabilities without knowing Megaplan-specific gate recommendations or override actions.
10. Keep temporary shims explicitly counted and failing M6 if still present.
