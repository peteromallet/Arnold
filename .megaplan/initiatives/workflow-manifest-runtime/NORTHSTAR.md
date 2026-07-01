# North Star

Arnold workflows compile to a durable `WorkflowManifest` and execute through a neutral runtime/kernel contract.

The manifest is the stable runtime/kernel contract, not the semantic authoring
truth for Megaplan. Product packages such as Megaplan register prompts,
policies, handlers, reducers, and control meanings around that contract; they
do not own the generic runtime architecture.

Reconciled doctrine: this initiative is runtime/kernel quarry for the current
native-representation program, not the governing Megaplan authoring end state.
For Megaplan, visible compositional Python workflow source is the semantic
authoring truth; `WorkflowManifest` is the normalized runtime, replay,
inspection, and interchange contract compiled from that source.

## What "Clean" Means

- `arnold.workflow`, `arnold.patterns`, `arnold.kernel`, and `arnold.execution` expose the neutral authoring, manifest, and runtime surfaces.
- Megaplan may use explicit-node manifest/data forms as migration or runtime
  substrate, but final Megaplan authoring must not require hand-authored
  manifest graphs when compositional Python source can express the workflow.
- Current supported Megaplan behavior is preserved through goldens, resume/state checks, chain behavior, CLI/operator checks, generated assets, and installed-wheel conformance.
- Old native-first assumptions are reconciled at the source, not hidden behind bridges.
- No permanent public `megaplan`, `arnold.pipelines.megaplan`, `_pipeline`,
  graph-era builder, `Stage`, `Edge`, `ParallelStage`, or compatibility shim
  surface survives the final state. Native composition surfaces and product
  package entrypoints remain valid when they are the canonical source authority
  defined by the current native-representation program.
- Runtime identity is derived from stable workflow identity plus manifest hash; replay, events, artifacts, discovery metadata, trust classification, and deletion gates agree on that identity.
- Loops, fanout, retry, subpipeline, suspension, control transitions, artifact hashes, resume cursors, and replay are manifest/runtime semantics rather than product-private conventions.

## Why This Matters

The native Python completion work proved a direction, but the durable end state is not a hidden product runner. The goal is a reusable Arnold workflow substrate that can express Megaplan and future pipelines with explicit source authority, compiled runtime manifests, deterministic replay, and clean package boundaries.
