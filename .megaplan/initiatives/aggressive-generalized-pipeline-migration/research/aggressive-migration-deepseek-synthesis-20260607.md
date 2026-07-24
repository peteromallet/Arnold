# Aggressive Arnold/Megaplan Migration: DeepSeek Synthesis

Date: 2026-06-07

This note synthesizes a 10-agent DeepSeek swarm requested to answer: what would an aggressive migration require on top of the foundations already present, and which parts of Megaplan/Arnold are already far enough along to reuse?

One branch-archaeology worker was stopped early after enough signal had landed. The synthesis uses the nine completed reports: substrate inventory, Megaplan privilege extraction, runner convergence, StepContract authority, boundary tests, proof pipelines, supervisor extraction, migration oracle, and epic shape.

## Core Answer

This is not a greenfield substrate build.

The repo already contains a serious Arnold substrate:

- `arnold.pipeline` has a working neutral graph/step/port/contract/executor layer.
- `arnold.runtime` has neutral envelope, operation, driver, batch, settings, recovery, and resume primitives.
- `arnold/pipelines/evidence_pack` is already a non-Megaplan proof pipeline with typed ports, parallel fan-out/reduce, suspension/resumption, contract results, and zero Megaplan imports.
- Megaplan is already relocated under `arnold.pipelines.megaplan`.
- There is existing oracle infrastructure: fold/WAL equivalence, replay oracles, substrate-swap oracles, hinge-gate topology parity, pipeline parity, evaluand/calibration replay, and dual-run oracle scaffolding.

The aggressive migration is therefore not "build the substrate." It is:

> Finish turning the existing substrate into the only blessed path, move privileged generic concepts out of Megaplan, and activate the platform pieces behind hard parity gates.

## What Already Exists And Should Be Reused

Reuse as load-bearing substrate:

- `arnold.pipeline.types`: `Pipeline`, `Stage`, `ParallelStage`, `Edge`, `Step`, `StepContext`, `StepResult`, `Port`, `PortRef`, `ContractResult`, `Suspension`, provenance/freshness carriers, routing/selection/reduce types.
- `arnold.pipeline.builder.PipelineBuilder`.
- `arnold.pipeline.contracts`: `ContractLedger`, `bind`, coercion and port-binding machinery.
- `arnold.pipeline.routing.resolve_edge`.
- `arnold.pipeline.contract_reduce`, `contract_validation`, `pattern_select`, `pattern_stops`, `pattern_joins`.
- `arnold.runtime.*` neutral carriers and protocols.
- `arnold/pipelines/evidence_pack/*` as the first proof pipeline.
- Existing oracle harnesses rather than new bespoke comparison scripts.

Reuse, but purify:

- `arnold/pipelines/megaplan/_pipeline/executor.py`: today this is the production-capable walker, with activation, I/O contracts, state merge, governor, typed ports, suspension, and policy hooks. It should not simply be thrown away in favor of the smaller neutral executor. Its capabilities should be moved/purified into the canonical Arnold executor behind injected hooks.
- `arnold/pipelines/megaplan/supervisor/*`: much of the data model and ladder policy is generic, but it currently lives inside Megaplan.
- `arnold/pipelines/megaplan/control_interface.py`: contains neutral carrier/protocol types mixed with Megaplan-specific bridge functions.

## What Is Still Missing

Concrete missing pieces:

- `arnold.control` package for neutral control carriers.
- `arnold.supervisor` package for neutral cross-run orchestration primitives.
- Authoritative `StepContract` registry.
- A purified canonical executor with hook injection.
- A thin runner API that delegates to the canonical executor.
- Strict boundary tests that prevent `.megaplan`, `MEGAPLAN_`, `GateRecommendation`, and `STATE_*` leaks into generic modules.
- A second non-Megaplan proof pipeline beyond `evidence_pack`.
- A formal migration oracle command set for each aggressive milestone.

## Main Corrections To The Earlier Plan

### 1. Canonical Executor

Earlier plan: make `arnold.pipeline.executor.run_pipeline` the canonical walker.

DeepSeek correction: the small neutral executor is currently not production-equivalent. The Megaplan `_pipeline/executor.py` is the real production walker. It should be purified and moved/converged into the generic executor, not ignored.

Current walker paths:

1. `arnold/pipeline/executor.py`: neutral, minimal, mostly used by tests and `evidence_pack`.
2. `arnold/pipelines/megaplan/_pipeline/executor.py`: production-capable Megaplan pipeline executor.
3. `arnold/pipelines/megaplan/auto.py`: legacy subprocess phase loop.
4. `arnold/pipelines/megaplan/drivers/in_process.py`: flag-gated driver path.

Aggressive target:

- one canonical executor in `arnold.pipeline`
- Megaplan-specific lifecycle behavior injected through hooks
- `auto.py` legacy loop retired only after dual-green replay
- compatibility shims kept temporarily, then deleted

### 2. Control Vocabulary First

The cleanest first extraction is `RunOutcome`.

Move:

- `RunOutcome`
- `RunResultMetadata`

From:

- `arnold/pipelines/megaplan/run_outcome.py`

To:

- `arnold/runtime/outcome.py` or `arnold/control/outcome.py`

Keep in Megaplan:

- batch outcome adapters
- driver-status normalization
- planning-state mappings

This is the lowest-risk proof that neutral concepts no longer belong to Megaplan.

### 3. StepContract Should Become Authoritative

Current step metadata is scattered across:

- `workers/_impl.py`: schema filenames
- `model_seam.py`: capture schema keys, compatibility modes, normalizers
- `prompts/__init__.py`: step/prompt builder maps
- `profiles/policy.py`: default routing
- ad-hoc `StepInvocation.metadata` dicts

Aggressive path:

1. Add `StepContract` mirror.
2. Derive old views from it.
3. Replace ad-hoc invocation metadata construction with contract factories.
4. Delete old dicts.
5. Add AST tests so no raw metadata construction returns.

The contract should include identity, schema key, capture schema key, output kind, compatibility mode, normalizer, and default prompt/routing references as needed. It should not own runtime model, provider, budget telemetry, prompt overrides, repair attempts, or output paths.

### 4. Boundary Tests Must Become Hard Gates

Existing boundary tests are useful but not strict enough.

Add tests that generic modules cannot contain:

- imports from `arnold.pipelines.megaplan`
- `.megaplan` path sentinels
- `MEGAPLAN_` env vars
- `GateRecommendation`
- `STATE_*`
- planning-specific default binding strings

Known current failures:

- `arnold/pipeline/schema_registry.py`
- `arnold/pipeline/step_io_policy.py`
- `arnold/pipeline/artifacts.py` compatibility bridge

These should be fixed before the broader extraction.

## Aggressive Epic Shape

### M0: Boundary Lock And Substrate Inventory

Outcome: make the existing substrate explicit and protected.

Deliverables:

- import/string leak tests for `arnold.pipeline`, `arnold.runtime`, new `arnold.control`, new `arnold.supervisor`
- inventory document of blessed primitives
- parameterized schema root and step-IO policy paths
- removal or quarantine of `.megaplan` assumptions from generic code

Gate:

- boundary tests pass
- `evidence_pack` remains zero-Megaplan-import

### M1: Neutral Outcome And Control Extraction

Outcome: generic run/control vocabulary no longer belongs to Megaplan.

Deliverables:

- `arnold.control` or `arnold.runtime.outcome`
- move `RunOutcome` and `RunResultMetadata`
- split neutral control carriers from Megaplan bridge functions
- re-export compatibility stubs from old Megaplan paths

Gate:

- all existing control tests pass
- no Arnold control/runtime module imports Megaplan

### M2: Authoritative StepContract

Outcome: one typed source of truth for Megaplan step metadata.

Deliverables:

- `arnold/pipelines/megaplan/step_contracts.py`
- registry for all planning steps
- derived schema/capture/compatibility/normalizer views
- invocation factory
- delete scattered dicts after parity

Gate:

- every current step has a contract
- old and new invocation metadata are byte-identical before deletion
- model seam and prompt routing tests pass

### M3: Executor Convergence

Outcome: one blessed executor path.

Deliverables:

- purified executor hooks
- production features from Megaplan executor moved behind neutral hook interfaces
- Megaplan runner delegates to canonical executor
- thin `run_step` / `run_pipeline_by_name` API

Gate:

- pipeline parity tests byte-match existing artifacts
- `evidence_pack` still runs on the canonical executor
- legacy executor remains behind compatibility shim until dual-green

### M4: Supervisor Extraction

Outcome: cross-run orchestration is generic; chain policy is Megaplan-specific.

Deliverables:

- `arnold.supervisor.model`
- `arnold.supervisor.ladder`
- generic run node/dependency/lifecycle carriers
- Megaplan chain adapter keeps YAML/Git/PR/profile policy

Gate:

- supervisor ladder tests pass through new package
- chain runner parity remains green
- no profile/robustness strings hardcoded in generic ladder

### M5: Oracle-Gated Strangler

Outcome: aggressive migration is protected by replay, not faith.

Deliverables:

- milestone-level oracle commands
- golden traces for recovery, escalation, blocked/resume, happy path
- artifact byte comparison where required
- semantic event/state comparison where timestamps and IDs differ

Gate:

- fold/WAL equivalence
- replay oracle
- topology parity
- dual-run oracle
- pipeline artifact parity

### M6: Second Proof Pipeline

Outcome: generalized substrate is not overfit to `evidence_pack` or Megaplan.

Deliverables:

- a second non-Megaplan pipeline, probably a tournament/multi-judge reducer promoted out of Megaplan demos
- formal acceptance tests for typed ports, fan-out/fan-in, suspension if applicable, contract results, artifact replay

Gate:

- zero Megaplan imports
- deterministic run
- deliberate port mismatch fails loudly
- same executor/runner API as Megaplan and `evidence_pack`

### M7: Megaplan As Flagship App

Outcome: Megaplan is a serious app on the Arnold substrate, not a privileged internal owner.

Deliverables:

- planning pipeline manifest
- Megaplan `build_pipeline()`
- bakeoff/chain/supervisor through generic orchestration where applicable
- compatibility shims deleted after dual-green

Gate:

- old and new Megaplan paths replay the same traces
- no internal Megaplan code imports deprecated compatibility paths
- active Evidence-First semantics still pass authority/provenance gates

## What Not To Do

- Do not build a new runner beside the existing walkers.
- Do not move Git/PR/merge policy into generic Arnold.
- Do not move Megaplan gate vocabulary into Arnold.
- Do not flip the active Evidence-First authority model before M0-M3 settle it.
- Do not delete the subprocess seam before engine/target isolation and first-slice proof are green.
- Do not rely on docs as proof; every migration milestone needs oracle evidence.

## Practical Sequencing With Evidence-First

Still finish Evidence-First M0-M3 before flipping this migration load-bearing.

Reason:

- M0 establishes engine/target isolation.
- M1 establishes the evidence contract.
- M2 migrates authority readers.
- M3 proves execute -> review -> done.

After that, this aggressive migration should start immediately and should shape later Evidence-First routing/control milestones rather than letting both efforts build competing abstractions.

## First Concrete PR

Start with `RunOutcome` extraction.

Files:

- add `arnold/runtime/outcome.py`
- update `arnold/runtime/__init__.py`
- keep `arnold/pipelines/megaplan/run_outcome.py` as compatibility re-export plus Megaplan-specific adapters
- update internal imports gradually
- add boundary tests proving `arnold/runtime/outcome.py` imports no Megaplan

Why first:

- tiny surface
- zero semantic risk
- proves the new ownership direction
- reduces coupling before larger control/supervisor moves

## Bottom Line

Be aggressive by activating and converging what already exists.

The current branch already has the foundations. The next epic should not be another planning-only cleanup. It should make Arnold the public substrate, force Megaplan onto it, and use existing oracle machinery to move fast without losing behavioral trust.
