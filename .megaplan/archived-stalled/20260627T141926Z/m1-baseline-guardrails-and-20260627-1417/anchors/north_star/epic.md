# North Star

Arnold workflows compile to a durable `WorkflowManifest` and execute through a neutral runtime/kernel contract.

The manifest is the stable contract. Product packages such as Megaplan register prompts, policies, handlers, reducers, and control meanings around that contract; they do not own the generic runtime architecture.

## What "Clean" Means

- `arnold.workflow`, `arnold.patterns`, `arnold.kernel`, and `arnold.execution` expose the neutral authoring, manifest, and runtime surfaces.
- Megaplan is migrated onto explicit-node manifest authoring and manifest execution.
- Current supported Megaplan behavior is preserved through goldens, resume/state checks, chain behavior, CLI/operator checks, generated assets, and installed-wheel conformance.
- Old native-first assumptions are reconciled at the source, not hidden behind bridges.
- No permanent public `megaplan`, `arnold.pipelines.megaplan`, `_pipeline`, `native_runner`, `native_hooks`, `PipelineBuilder`, `Stage`, `Edge`, `ParallelStage`, or compatibility shim surface survives the final state.
- Runtime identity is derived from stable workflow identity plus manifest hash; replay, events, artifacts, discovery metadata, trust classification, and deletion gates agree on that identity.
- Loops, fanout, retry, subpipeline, suspension, control transitions, artifact hashes, resume cursors, and replay are manifest/runtime semantics rather than product-private conventions.

## Why This Matters

The native Python completion work proved a direction, but the durable end state is not a hidden product runner. The goal is a reusable Arnold workflow substrate that can express Megaplan and future pipelines with explicit contracts, deterministic replay, and clean package boundaries.
