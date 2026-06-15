# Elegant Arnold/Megaplan Architecture Plan

## Where The Thinking Landed

The goal is not to move Megaplan internals into a new namespace. The goal is to
make agentic workflows easy for agents to author, easy for operators to trust,
and easy for product packages to specialize.

The current best shape is:

```text
1. Arnold Kernel
   Hard runtime guarantees.

2. Arnold Python Workflow DSL
   A small agent-readable Python authoring surface.

3. Arnold Authoring And Inspection Tools
   Validation, dry runs, generated views, graphs, capability diffs.

4. Arnold Pattern Library
   Reusable workflow blocks such as critique, fanout, review, fact_check.

5. Pipeline Packages
   Megaplan, legal diligence, source-grounded writing, canary rollout, etc.
```

This is not the original "one generic Megaplan-shaped executor" plan. It is also
not an ultra-thin substrate that leaves every pipeline to reinvent durability,
events, artifacts, human gates, and idempotency. It is a durable execution
substrate plus a concrete Python workflow DSL and a rich pattern library.

Getting there is a strangler migration, not a namespace move. The current repo
still carries Megaplan-shaped imports, state files, handlers, event sidecars,
worker assumptions, and compatibility surfaces. The plan treats those as inputs
to the migration sequence rather than as a separate caveat.

The current branches have already implemented a large amount of this direction.
That changes the plan from "start from zero" to "quarry aggressively without
inheriting accidental shape." The right base is a fresh branch from
`origin/main`, because `origin/main` already contains `arnold-epic`. The
newer `arnold-generalized-pipeline` branch is a quarry and testbed, not the
base: it contains valuable neutral runtime, pipeline, agent, conformance, cost,
and non-Megaplan pipeline work, but it also commits generated
`.megaplan/_archived-plans` artifacts and collapses several target layers into
one broad `arnold/pipeline` surface.

The slogan:

```text
Kernel primitives are few and boring.
Python workflow DSL is stable and ergonomic.
Authoring tools make errors repairable and behavior inspectable.
Patterns are rich and reusable.
Pipeline packages are opinionated.
```

## Why This Shape

The architecture has to work for many more workflows than Megaplan:

- plan, critique, revise, execute, and review a software change;
- draft a source-grounded article with claim-level provenance;
- run ten critics over a plan, merge them, revise, and repeat;
- review a legal data room with human-approved red flags;
- run canary deployments with rollback and audit trails;
- generate differentiated curriculum paths for students;
- audit scientific claims through adversarial reproduction trials;
- turn product signals into investment memos.

These workflows share hard execution needs:

- durable run identity;
- artifacts that survive agent process lifetimes;
- append-only events and causal replay;
- agent dispatch with provenance;
- capability and sandbox enforcement;
- cost and token accounting;
- human decisions that suspend and resume work;
- external side-effect fencing and idempotency;
- observability that works across local and cloud runs.

They do not share one domain meaning for "critique", "gate", "review",
"completion", "receipt", or "state merge". Those meanings should be reusable
where useful, but not hardwired into the kernel.

## Target Package Shape

The exact names can change, but the dependency direction should not.

```text
arnold/
  kernel/
    run.py             # RunEnvelope, run identity, lifecycle
    artifacts.py       # content-addressed artifacts and refs
    events.py          # append-only causal event journal
    provenance.py      # model/tool/process provenance
    capabilities.py    # declared powers and policy checks
    human.py           # await_human_decision primitives
    side_effects.py    # intent/fulfillment/compensation fencing
    cost.py            # cost/token/resource accounting envelope
    store.py           # neutral blob/store contracts

  agent/
    contracts.py       # AgentRequest, AgentResult, AgentSpec, usage, traces
    dispatch.py        # dispatch protocol and provider adapter boundary
    keys.py            # key/provider access protocol
    tools.py           # tool registry and capability binding

  workflow/
    dsl.py             # Python authoring surface
    compiler.py        # Pipeline object -> orchestrator plan
    validation.py      # schema, capability, event, artifact checks
    refs.py            # state/artifact/input expression refs
    inspect.py         # generated views, graphs, summaries
    dry_run.py         # execution preview and capability diff

  patterns/
    agent.py
    fanout.py
    merge.py
    branch.py
    loop.py
    critique.py
    review.py
    fact_check.py
    human_gate.py
    external_call.py
    provenance_bundle.py

  execution/
    dag.py
    state_machine.py
    saga.py
    choreography.py
    external.py

  conformance/
    imports.py
    capabilities.py
    replay.py
    side_effects.py
    adapters.py

arnold_pipelines/
  megaplan/
    templates/
    policies/
    receipts/
    cli.py

  source_grounded_draft/
  legal_diligence/
  canary_rollout/
```

The current Megaplan pipeline code cannot be copied into these packages as-is.
Current types, stages, builder helpers, executor branches, and handler wrappers
still encode phase handlers, gate recommendations, tiebreakers, `PlanState`, and
`.megaplan` assumptions. Extraction means neutralizing those seams behind
contracts and adapters, not moving files into `arnold/` unchanged.

## Current Quarry Map

This plan is now anchored to the branch-transplant decision record in
`docs/arnold/branch-transplant-audit.md`. Six DeepSeek branch auditors inspected
the loose Arnold, Megaplan engine, test-selection, attribution, Shannon, and
stash surfaces; the results were then spot-checked manually. Their outputs are
raw evidence, not authority. The audit document is the decision layer for what
to port, defer, reject, preserve, or leave alone.

The audit resolves the immediate loose-branch issue: none of the Megaplan
engine, test-selection, attribution, Shannon, or stash material should change
the Arnold extraction base. The panel-dispatch Codex/Shannon adapter payload
has now landed as a Megaplan-package adapter slice. The artifact IO and resume
re-verification primitives have also landed, and evidence-pack now owns the
first concrete package-level resume driver. The rejected path is a broad
neutral `run_pipeline_resume()` with WAL replay and cursor-body authority.
Remaining Arnold-relevant quarry is incremental and named: selected
`arnold-generalized-pipeline`
discovery/validator/routing/effect candidates,
possible same-graph entry override only after another package proves the need,
and dirty conformance-gate execution hardening that must be preserved before
any cleanup.

### Build Base

Build the clean port from `origin/main`, currently `3c538a95`. Do not use local
`main`, which is stale, and do not base the work on the current dirty
`fix/finalize-readiness-deadturn-and-baseline-cache` checkout or on
`arnold-generalized-pipeline`.

`origin/main` already contains `arnold-epic` and these Arnold foundations:

- initial neutral pipeline primitives under `arnold/pipeline/`;
- neutral runtime carriers under `arnold/runtime/`;
- a full Megaplan plugin under `arnold/pipelines/megaplan/`;
- initial docs, CLI tests, and package-boundary tests.

The main gaps on `origin/main` are the neutral agent subsystem, control package,
conformance package, event journal/WAL/semantic replay, side-effect fence,
neutral cost/media model, and namespace decontamination.

`arnold/pipelines/megaplan` is today's nested reality, not the final dependency
shape. The target peer package is `arnold_pipelines.megaplan`. During migration,
the nested package can remain as a compatibility import path, but it should be a
shim over the peer package once the move starts. Conformance gates must be aware
of both names during the transition so a package rename does not make the gate
silently blind.

### Direct-Port Candidates

Direct-port does not mean "merge the branch." It means the concept and most of
the implementation fit the target after normal integration review.

| Source | Quarry | Why It Fits |
| --- | --- | --- |
| `arnold-generalized-pipeline` | `arnold/runtime/event_journal.py`, `state_persistence.py`, `wal_fold.py`, `semantic_replay.py`, `oracle.py`, `effect.py` | Kernel-shaped durability, replay, recovery, and side-effect ingredients. |
| `arnold-generalized-pipeline` | `arnold/agent/contracts.py`, `dispatcher.py`, `providers/pool.py` | Neutral agent request/result/provider boundary. |
| `fix/arnold-conformance-gate` | `arnold/conformance/` | Import-leak ratchet and conformance runner. |
| `fix/arnold-neutralize-canonicalusage` | `arnold/pipeline/cost_types.py`, `media_cost.py`, `token_cost.py` | Neutral cost and media usage surface. |
| `arnold-generalized-pipeline` | `arnold/pipelines/deliberation/`, `arnold/pipelines/evidence_pack/` | Serious non-Megaplan proof pipelines. |
| dirty `arnold-panel-dispatch` worktree | `arnold.pipelines.megaplan.agent_adapters`, adapter tests, and worker `free_text` support | Consumed by Slice 14 as Megaplan-package adapters. Remaining Hermes/Honcho relocation is parked. |

### Reshape-Port Candidates

These are valuable but must be reclassified before landing.

| Source | Quarry | Required Reshape |
| --- | --- | --- |
| `arnold/pipeline/types.py`, `builder.py`, `executor.py` on newer branches | `Pipeline`, `Stage`, `Edge`, `StepResult`, `PipelineBuilder`, walk-loop executor | Treat as compiler IR and certified backend material, not the public Python DSL. |
| `arnold/pipeline/artifacts.py` | Versioned artifact mechanics | Move toward content-addressed immutable artifact refs; avoid stage/label path semantics as the final kernel contract. |
| `arnold/runtime/event_journal.py` | NDJSON journal mechanics | Do not preserve `phase` as kernel vocabulary; pipeline-owned metadata only. |
| `arnold/pipelines/megaplan/runtime/capabilities.py` | Capability registry ideas | Extract neutral capability registry and provider backends; keep container/human specifics in Megaplan. |
| `arnold/pipelines/megaplan/orchestration/completion_contract.py` | Evidence-oriented completion logic | Extract evidence collection/verification primitives; keep Megaplan verdict semantics in Megaplan. |
| `arnold/pipelines/megaplan/_pipeline/*` | Megaplan graph, loops, topology helpers | Collapse duplicates into imports from `arnold.patterns` and `arnold.execution` where truly generic. |

### Layer Translation Map

The existing `arnold/pipeline` tree is useful but too flat. Use this translation
map when porting:

| Existing Area | Target Layer |
| --- | --- |
| `artifacts.py`, artifact manifests, immutable refs, cost/media/token accounting, event journal, side-effect intent/receipt, run/outcome/envelope pieces | `arnold.kernel` |
| `types.py` public declarations, refs, validation, schema registries, content validation, compiler/lowering | `arnold.workflow` |
| `builder.py`, `Stage`, `Edge`, `ParallelStage`, `StepResult.next`, current graph walk-loop structures | internal workflow IR or `arnold.execution` backend internals |
| `executor.py`, `runner.py`, routing, resume, hook protocol, backend certification | `arnold.execution` |
| `pattern_select.py`, `pattern_stops.py`, `pattern_joins.py`, `pattern_dynamic.py`, `subpipeline.py`, human-gate wiring | `arnold.patterns` when policy-neutral; package-local incubation otherwise |
| Megaplan-specific contracts, handlers, topology, receipts, state, prompts, profile slots | `arnold_pipelines.megaplan` plus compatibility shims |

The authoritative neutral agent tree is `arnold.agent`. The existing
`arnold.pipelines.megaplan.agent` tree is pipeline-owned compatibility and
runtime integration code during migration. New neutral contracts, providers,
dispatchers, and lazy adapters should land in `arnold.agent`; Megaplan-specific
worker adapters can call into Megaplan lazily but should not make importing
`arnold.agent` import the Megaplan worker tree.

### Clean Extraction Progress

The clean branch is now no longer a standing start. It has selectively ported
these quarry slices:

- **Slice 1: static conformance gates** — import coupling, package-name
  staleness, semantic coupling, public workflow layering, and never-port
  artifact checks.
- **Slice 2: neutral cost/media/token accounting** — usage and cost carriers,
  media metadata validation, media usage normalization, and injectable token
  pricing helpers without baked live provider pricing.
- **Slice 3: runtime event durability** — append-only NDJSON event journal,
  atomic state writes, pure WAL fold, and semantic replay.
- **Slice 4: neutral agent contracts and dispatcher** — `AgentRequest`,
  `AgentResult`, `AgentSpec`, fanout units, `ArnoldDispatcher`, adapter
  protocols, and provider key-pool/env-loader primitives.
- **Slice 5: Megaplan StepContract registry** — a package-local registry for
  the 17 Megaplan phase identities, with byte-parity tests against the current
  legacy literals.
- **Slice 6: pipeline hooks and runner** — the neutral `ExecutorHooks`
  protocol, no-op defaults, opt-in media-cost helper, thin runner namespace,
  hook-aware executor insertion points, hook metadata, hook extensions, and
  package exports. Resume re-verification and typed Step-IO enforcement remain
  deliberately deferred.
- **Slice 7: Megaplan StepContract cutover** — legacy Megaplan phase metadata
  maps in `workers/_impl.py`, `profiles/policy.py`, and `model_seam.py` now
  derive from the StepContract registry. `CompatibilityMode` was extracted to
  a leaf module to break cycles, `audit_step_payload()` uses
  `contract_to_invocation()` for registered phases, and AST guards prevent
  reintroducing duplicate literals or minimal invocation bypasses.
- **Slice 8: behavioural routing and join conformance** — direct-ported
  routing vocabulary/edge checks, seeded `resolve_edge` behavioural checks,
  join-delegation checks, and opt-in `run_conformance_suite(pipelines=...,
  hooks=...)` wiring. Static conformance remains the default five-check mode.
- **Slice 9: evidence-pack runtime hooks** — `EvidencePackHooks` now uses the
  neutral executor hook surface to persist events, state snapshots, and
  suspension cursors for the concrete evidence-pack pipeline. This proves Slice
  3 durability primitives and Slice 6 hooks compose outside Megaplan.
- **Slice 10: neutral runtime surface cleanup** — an adversarial quarry audit
  found compatibility leftovers in the runtime substrate. The clean branch now
  removes `plan_state_lock`, `read_event_journal_paged`, `expected_plan`, and
  the event-journal `phase` field/argument. `arnold.runtime.__init__` now
  exports only shipped runtime primitives instead of aspirational batch,
  recovery, and driver APIs.
- **Slice 11: typed Step-IO executor wiring** — the neutral executor now uses
  the existing Step-IO classifier at state/output write boundaries and exposes
  typed envelope payloads through `StepContext.inputs` while preserving the raw
  state view. Legacy values remain allowed; invalid or schema-unavailable
  typed envelopes are blocked before entering executor-owned state.
- **Slice 12: agent backend adapter protocol** — `BackendAdapter` is now a
  runtime-checkable callable Protocol instead of a bare `Callable` alias. This
  keeps function and class adapters valid while giving concrete DeepSeek/Codex
  adapter ports a named structural seam to target.
- **Slice 13: DeepSeek adapter reshape** — the first concrete provider adapter
  now targets the neutral `BackendAdapter` seam directly. It uses a
  stdlib/OpenAI-compatible chat-completions transport, injected `KeyPool`,
  injected pricing rows through `arnold.pipeline.token_cost`, and does not
  import the quarry `run_agent` monolith, provider SDKs, or baked `_pricing.py`.
- **Slice 14: Megaplan Codex/Shannon adapter reshape** — Codex and Shannon
  one-shot wrappers now live under `arnold.pipelines.megaplan.agent_adapters`,
  because they depend on Megaplan worker internals. They implement the neutral
  `AgentRequest`/`AgentResult` seam, add additive worker `free_text=False`
  support, avoid root/default registration, and preserve `import arnold.agent`
  as a Megaplan-free contract import.
- **Slice 15: neutral resume cursor helpers** — `arnold.pipeline.resume`
  provides atomic cursor persistence helpers and evidence-pack now uses them.
- **Slice 16: artifact IO chokepoint and sidecars** — `arnold.pipeline` now
  has a policy-effective artifact IO chokepoint plus large-artifact sidecar
  manifests and validation helpers.
- **Slice 17: resume re-verification helpers** — `arnold.pipeline` now parses
  `x-arnold-resume` declarations, resolves declared artifacts without
  consulting cursor bodies, and validates resumed artifacts through artifact IO
  and media-reference validators.
- **Slice 18: evidence-pack resume driver** —
  `arnold.pipelines.evidence_pack.resume_evidence_pack()` resolves persisted
  package cursors, validates the only legal re-entry stage, seeds explicit
  `human_input`, optionally calls `reverify_resume_produces()` for a supplied
  human suspension, and runs the continuation pipeline as a fresh normal
  `run_pipeline()` call. The neutral executor remains a graph runner, not a
  replay/resume authority.
- **Slice 19: neutral LLM JSON extraction** — `arnold.pipeline.llm_json`
  provides `parse_llm_json()` for clean JSON, fenced JSON, and embedded JSON
  object extraction from raw model output. This is a small prerequisite for
  agent-authored pipelines and future model-seam extraction, not a port of the
  larger Megaplan model seam.
- **Slice 20: adapter-registry-aware validation** — `arnold.pipeline.validator`
  now lets callers pass a `StepInvocationAdapterRegistry` into `validate()` and
  `validate_invocation_requirements()`. Default validation remains fail-closed
  with only the reserved `model` slot, while package-owned invocation kinds can
  prove their adapters explicitly.
- **Slice 21: neutral model seam submodule** —
  `arnold.pipeline.model_seam` now hosts generic model render/capture/budget
  and structural-audit primitives with step-keyed hook registries. It is a
  neutral submodule, not a root `arnold.pipeline` export, so it avoids circular
  imports and does not pull Megaplan schemas or step contracts into the kernel.
  Megaplan wrapper/re-export compatibility remains package-local follow-up
  work.
- **Slice 22: Megaplan model seam wrapper compatibility** —
  `arnold.pipelines.megaplan.model_seam` now wraps/re-exports the generic
  `arnold.pipeline.model_seam` primitives while keeping Megaplan schemas,
  prompt helpers, recovery, and compatibility-mode guards package-local. The
  wrapper preserves the local execute-receipt normalization guard and proves
  identity/parity against the generic seam.
- **Slice 23: generic subpipeline child context cloning** —
  non-dataclass child contexts now clone arbitrary parent attributes and
  override only `artifact_root` and `inputs`. This preserves package-owned
  runtime/capability fields without forcing the neutral subpipeline helper to
  know their names.
- **Slice 24: neutral panel aggregation join** —
  `aggregate_panel_join()` now gives fan-out panels a policy-free aggregation
  primitive: preserve child outputs, sum caller-named numeric usage fields, and
  emit a caller-owned next label.
- **Slice 25: neutral runtime/control carriers** —
  `ArnoldError`, `RunOutcome`, `RunResultMetadata`, and neutral
  `arnold.control` target/transition/result carriers now live outside the
  Megaplan package. This creates the shared vocabulary needed by future
  control-plane bindings without importing Megaplan semantics.
- **Slice 26: profile structured-value validators** —
  profile loading can now accept package-owned structured values for declared
  stages only when the caller provides an explicit validator. The default
  remains fail-closed to plain string agent specs.
- **Slice 27: schema registry decontamination** —
  neutral schema registry root resolution now uses explicit roots or
  `ARNOLD_CONTRACT_SCHEMA_ROOT`. It no longer treats `.megaplan/plans/<plan>`
  as a project-root signal and no longer exposes `MEGAPLAN_CONTRACT_SCHEMA_ROOT`
  from neutral Arnold code.
- **Slice 28: neutral process primitives** —
  `arnold.runtime.process` now owns `spawn`, `spawn_async`, and `kill_group`
  with explicit-argv process-group defaults. Tmux session/orphan helpers remain
  Megaplan-package runtime code.
- **Slice 29: neutral sandbox validators** —
  `arnold.runtime.sandbox` now owns sandbox ContextVar access and pure path
  validators for terminal commands, write paths, and V4A patches. Tool-registry
  wrapper installation remains package-owned.
- **Slice 30: neutral suite delta** —
  `arnold.pipeline.suite_delta` now provides pure nodeid-level
  baseline-versus-verification diffing. Deleted tests are tracked separately
  and cannot be reported as newly passing.
- **Slice 31: neutral static authoring checks** —
  `arnold.pipeline.c4_static_checks` now provides structured static findings,
  structural-subset validation for schema-like declarations, binding-map port
  checks, schema-shape checks, and optional caller-supplied adapter-registry
  call-site checks. The quarry branch's media-pricing advice and global
  default-registry assumption were intentionally not ported.
- **Slice 32: conformance ratchet cleanup and full-suite readiness** —
  the stale `semantic-coupling arnold.pipeline.schema_registry` allowlist entry
  was removed after schema-registry decontamination. `python-dotenv` is already
  declared in `pyproject.toml` and installed in the project interpreter; run the
  full Arnold suite through that interpreter:

  ```text
  python -m pytest tests/arnold -q
  1469 passed in 84.22s (0:01:24)
  ```

The latest DeepSeek quarry scan split the remaining quarry into this sequence:

1. **Package-level resume integration** has landed for evidence-pack. Do not
   port the quarry branch's broad neutral `run_pipeline_resume()`; cursor body
   interpretation, WAL replay, and state authority belong to concrete package
   drivers unless repeated package evidence proves a smaller neutral
   entry-override helper is needed.
2. **Concrete agent adapter/runtime reshape** has landed for DeepSeek as a
   neutral provider adapter and for Codex/Shannon as Megaplan-package worker
   adapters. Do not backslide into importing `run_agent.py`, provider SDKs,
   baked pricing tables, root adapter exports, or import-time default
   registration.
3. **Proof pipelines**: `evidence_pack` is already the useful non-Megaplan
   proof pipeline. The deliberation pipeline is a target/design, not a ready
   direct port; the latest branch audit found no concrete deliberation package
   to port. Do not invent it ahead of the agent/profile/registry substrate.
4. **Concrete agent runtime/tooling** must be reshaped. Do not port the huge
   `run_agent.py`, import-time tool self-registration, Hermes CLI, gateway,
   Honcho, or environment runners wholesale. Extract pure helpers and thin
   bindings in later slices.
5. **Kernel capability / side-effect / oracle material** in
   `arnold-generalized-pipeline` remains potentially valuable, but all of it
   is reshape-port work. It should not block the resume or adapter slices.
6. **Subpipeline context cloning** has landed as a small generic fix. Further
   subpipeline work should wait for a second package to prove the need for
   same-graph entry override or richer child-run semantics.
7. **Panel aggregation join** has landed as the only remaining generic
   `pattern_joins.py` delta. Further join work should stay package-local unless
   another reusable reducer shape appears.
8. **Runtime/control carriers** have landed as the smallest useful control
   stack. Remaining target-only runtime files are deferred:
   effect/oracle/supervisor code should wait for concrete runtime callers.
9. **Profile structured-value validation** has landed. Further profile work
   should be driven by concrete package profile shapes rather than adding a
   second declarative format.
10. **Schema registry root resolution** has been decontaminated. If Megaplan
    still needs plan-dir-to-project-root behavior, that adapter belongs in the
    Megaplan package, not in `arnold.pipeline.schema_registry`.
11. **Process primitives** have landed.
12. **Sandbox path validation** has landed. Wrapper installation and package
    tool integration remain outside neutral Arnold unless a second package
    needs the same wrapper contract.
13. **Suite delta** has landed as a pure testing utility. Any richer suite
    runner, retry, or CI integration should stay package-owned until multiple
    packages need the same runner contract.
14. **Static authoring checks** have landed as a neutral declaration analysis
    helper. Further checks should stay here only when they inspect Arnold
    declarations themselves; product pricing, Megaplan execution policy, and
    replay/runtime authority checks belong to the owning package.
15. **Full-suite readiness** has been established with `python -m pytest`, not
    an ambient global `pytest` executable. The project already declares
    `python-dotenv`; the earlier collection failure was an interpreter mismatch,
    followed by a stale conformance allowlist entry that is now removed.

After Slice 31, the remaining quarry material is not a reason to keep
transplanting into the clean branch:

- `arnold/pipeline/_cli_check.py` is rejected for now. It is a fixture CLI over
  the static checker and still includes the media-pricing warning path that the
  neutral static checker intentionally dropped.
- `arnold/pipeline/steps/human_gate.py` is deferred for re-authoring. A
  reusable human interaction step may be valuable, but the quarry file is stale
  against the current `ContractResult` / `Suspension` surface and should not be
  copied.
- `arnold/pipelines/deliberation/*` is deferred as a package example. It proves
  that layered critique pipelines fit the model, but it is a concrete workflow,
  not an Arnold substrate primitive.
- Broad `arnold/agent/**`, Hermes CLI, Honcho integration, environment tools,
  and tool registries are rejected for neutral Arnold. The useful adapter seam
  pieces have already landed in smaller DeepSeek/Codex/Shannon shapes.
- `arnold/pipelines/megaplan/_pipeline/adapter.py`, `hooks.py`, and related
  adapters are Megaplan integration work. They belong in the package wiring
  milestone once Megaplan is deliberately moved onto the canonical executor.

## Next Megaplan Sequence

The extraction branch is now a full-suite-green base. The next work is no
longer "port more useful quarry"; it is a post-extraction epic captured at
`.megaplan/briefs/arnold-post-extraction-next/chain.yaml`.

| Milestone | Brief | Size | Recommended run |
| --- | --- | --- | --- |
| M1: Megaplan canonical executor bridge | `.megaplan/briefs/arnold-post-extraction-next/m1-megaplan-canonical-executor-bridge.md` | One sprint | `partnered/full/high +prep` |
| M2: Package authoring surface | `.megaplan/briefs/arnold-post-extraction-next/m2-package-authoring-surface.md` | One sprint | `partnered/full/medium` |
| M3: Human interaction and deliberation package | `.megaplan/briefs/arnold-post-extraction-next/m3-human-interaction-and-deliberation-package.md` | One sprint | `partnered/full/medium` |
| M4: Megaplan package hardening | `.megaplan/briefs/arnold-post-extraction-next/m4-megaplan-package-hardening.md` | One sprint | `directed/full/medium` |
| M5: Branch retirement and compatibility cutover | `.megaplan/briefs/arnold-post-extraction-next/m5-branch-retirement-and-compatibility-cutover.md` | Small sprint | `solo/light/low` |

Run M1 first. It is the load-bearing next step because it proves Megaplan can
consume the neutral Arnold substrate through package-owned adapters/hooks. M2
should not run before M1, because the authoring surface needs a real package
bridge to teach from. M3 should not run before M2, because the human-gate and
deliberation decisions need the package authoring contract. M4 is deliberately
later so test-selection, attribution, and execution hardening land in the
Megaplan package after the package boundary exists. M5 is mechanical cleanup
after useful payloads are landed or rejected.

Suggested M1 command:

```text
megaplan init .megaplan/briefs/arnold-post-extraction-next/m1-megaplan-canonical-executor-bridge.md --profile partnered --robustness full --depth high --with-prep --prep-direction "Start from the full-suite-green Slices 1-32. Focus on the smallest representative Megaplan path that can run through arnold.pipeline.run_pipeline via package-owned adapters/hooks. Compare existing Megaplan executor behavior to the neutral executor hook surface before proposing replacements. Do not copy quarry bridge files wholesale."
```

Megaplan-prep sizing rationale:

- The whole post-extraction program is bigger than a single megaplan because it
  contains multiple architectural decisions with different stakes and ordering.
  Treat it as an epic.
- M1 is cross-cutting integration work with real compatibility risk, but the
  substrate decisions are already locked and objective gates exist. That points
  to `partnered`, not `premium` or `apex`.
- M1 earns `--with-prep` because the planner must trace the current Megaplan
  executor, CLI, hook, artifact, and compatibility surfaces before choosing the
  representative bridge path.
- `full` robustness is enough for M1: critique/revise/review matter, but
  `thorough` would mostly re-check already settled substrate decisions.
- `high` depth is for the planner's repo-reading load; critic/review can remain
  at the profile's normal low depth.
- M5 is `solo/light/low` because it is mechanical cleanup behind explicit
  branch-retirement criteria and test gates.

The delete-branch criterion is intentionally strict: the
`arnold-generalized-pipeline` branch becomes safe to delete only when every
useful quarry area has one of three documented dispositions in this plan and
ledger:

- ported into the clean branch with verification;
- deliberately deferred with the required reshape and target slice named;
- explicitly rejected as generated artifact, compatibility churn, or
  package-specific noise.

The migration state is:

```text
Today:
  arnold.pipeline/*                 # flat mix of workflow, patterns, execution
  arnold.pipelines.megaplan/*        # real Megaplan implementation
  megaplan/*                         # public compatibility/product surface

Intermediate:
  arnold.kernel|workflow|patterns|execution/*  # extracted neutral layers
  arnold_pipelines.megaplan/*                  # real Megaplan implementation
  arnold.pipelines.megaplan/*                  # shim import path
  megaplan/*                                   # CLI/import/artifact compat shim

Target:
  arnold/*                         # neutral substrate only
  arnold_pipelines.megaplan/*       # product package
  named compatibility shims only while telemetry requires them
```

### Tests And Design Only

Use these for shape, tests, and regression coverage, not as final source layout:

- `.megaplan/briefs/*` and archived plan docs from Arnold branches;
- existing `PipelineBuilder` examples that show useful agent-authored workflows
  but expose the wrong public layer;
- `mp-test-blast-radius` and `mp-tbr-merge`, which are useful Megaplan package
  hardening but not Arnold prerequisites;
- Shannon stream branches, which may matter later for worker UX but are not part
  of the Arnold substrate decision.

### Never-Port Material

Do not port generated or per-run artifacts:

- `.megaplan/_archived-plans/**`;
- `.hermes_state/**`;
- `*.db`, `*.db-shm`, `*.db-wal`;
- `.events.*`, `events.ndjson`, routing ledgers, receipts, phase state, prompt
  dumps, `tmux_session.json`, `empty_mcp_config.json`, and driver logs.

The generalized branch has 209 committed archived-plan files. Its `.gitignore`
negates `.megaplan/` and then fails to re-ignore `_archived-plans`; fix that
before any extraction branch can be trusted.

### Dirty Worktree Capture

Before deleting or pruning branches/worktrees, capture these unique pieces:

- `/private/tmp/arnold-target`: local `arnold-generalized-pipeline` is ahead of
  `origin/arnold-generalized-pipeline` by five commits, including
  `5ea1f70a`, `4544c94d`, merge commits, and `b1ed2225`.
- `/Users/peteromalley/Documents/.megaplan-worktrees/arnold-panel-dispatch`:
  unique adapter files, adapter tests, and `free_text` worker support.
- `/Users/peteromalley/Documents/.worktrees/arnold-conformance-gate`: unique
  dirty Step-IO, telemetry, in-process contract, and test updates.
- `fix/engine-bug-ledger` commit `41571fcd`: cost/provenance events for
  Codex-routed execute tasks, not contained in the current integration branch.

Do not delete `arnold-generalized-pipeline` until every direct-port,
reshape-port, tests-only, and never-port item above has been explicitly checked
off and the local-only commits have either landed or been intentionally
abandoned.

## The Arnold Kernel

The kernel owns invariants that every serious pipeline should get for free.

### Run Envelope

Every pipeline run gets a durable envelope:

- run id;
- pipeline id and version;
- root artifact namespace;
- engine root and target root;
- policy/capability manifest;
- model/provider configuration;
- clock, host, process, and workspace provenance;
- parent/child run relationships.

The run envelope is the anchor for status, replay, cost, artifact retention, and
auditing.

### Artifact Store

Artifacts should be content-addressed, immutable, version-linked, and scoped to
the pipeline instance rather than the producing agent process.

This supports:

- downstream agents reading artifacts after the producer exits;
- cache validation by artifact hash;
- replay without duplicating artifacts;
- live-run patching through new artifact versions rather than mutation;
- provenance bundles that point to stable artifact refs.

### Event Journal

The event journal is append-only truth. State snapshots, dashboards, traces,
receipts, and doctor commands are projections over it.

Events should cover:

- run and stage lifecycle;
- agent dispatch and completion;
- artifact writes;
- state checkpoints;
- routing decisions;
- model/provider/cost records;
- capability grants and denials;
- human decision requests and injections;
- external side-effect intents and fulfillments;
- retries, suspensions, waivers, overrides, and failures.

Operator interventions are not side channels. Overrides, waivers, manual
retries, and forced transitions should be appended as operator-originated
events and folded into state.

This is a target invariant, not a claim about current Megaplan. Today,
`state.json`, routing ledgers, receipts, chain state, phase result files, and
events are written through multiple paths. The migration must measure and close
event-to-state replay divergence instead of assuming events are already causal
truth.

### Agent Contracts

Arnold should expose neutral agent contracts:

- `AgentRequest`;
- `AgentResult`;
- token/cost usage;
- model/provider actuals;
- session/provenance records;
- tool/capability grants;
- trace output and artifact refs.

The agent contract must not require Megaplan profile slots such as `plan`,
`critique`, `gate`, or `review`. Those are product/template concerns.

### Capability Enforcement

Authority should be explicit, not ambient. Capability categories should include:

- agent dispatch;
- shell execution;
- file write;
- key/provider access;
- network/web/browser access;
- thread/process fanout;
- sandbox escape or host interaction;
- human suspension/approval;
- external side effects.

The runtime checks capabilities before executing steps, acquiring keys, spawning
processes, installing tools, writing files, or invoking external systems.

Worker isolation must be proven at the same boundary. Existing protections
around process groups, tmux isolation, Codex sandboxing, and worker env handling
are useful but incomplete. The kernel must explicitly cover cwd selection,
symlink resolution, package-resolution leaks, editable installs, tool writes,
and worker-specific differences across Hermes, Shannon, Codex, and future
workers.

### Human Decision Primitive

Human-in-the-loop is common enough to be core, but the domain meaning belongs to
the pipeline.

Arnold should provide a primitive like:

```python
human_gate(
    id="partner_review",
    subject=artifact("review_packet"),
    decision_schema=PartnerReviewDecision,
    deadline=hours(48),
    escalation=partner_review_queue,
)
```

The kernel owns durable suspension, authenticated reviewer identity, deadline
awareness, decision injection, and audit events. The product owns the review
queue UX, schema vocabulary, and meaning of the decision.

Current Megaplan decision concepts are scattered across overrides, waivers,
verification, feedback, bakeoff picks, chain policies, and blocked states. Those
surfaces should inform the record shape, but Arnold should expose one primitive:
durable suspension plus typed decision injection as an auditable event.

### Side-Effect Fence

Any step that touches external state should pass through an intent/fulfillment
contract:

```text
persist intent -> invoke or check fulfillment -> persist receipt -> compensate if needed
```

The kernel owns idempotency keys, intent records, replay checks, fulfillment
receipts, and compensation hooks. The pipeline owns the domain-specific action:
posting to Slack, pushing an insertion order, creating a Notion doc, deploying a
canary, or sending an email.

This is mostly new architecture. The repo has useful ingredients, including
store idempotency keys, receipt writers, some git compensation, and cloud
delivery guards, but no unified fence. Land one real fenced path before treating
side-effect safety as part of the substrate.

## Python Workflow DSL

Agents need a concrete format they can author quickly. That format should be
Python, not a second YAML/config language.

The source of truth for a serious pipeline should be a normal Python module,
usually `pipeline.py`. That avoids duplicated representations and keeps the
pipeline close to real imports, types, tests, custom policy functions, custom
side-effect handlers, and package-local helpers.

A pipeline definition should describe:

- named inputs;
- durable state fields;
- artifact declarations;
- capability declarations;
- steps and patterns;
- routing;
- human gates;
- external side effects;
- emitted receipts/status views.

For production Megaplan parity, the DSL must support more than boolean
branching. It needs typed multi-way dispatch, subpipeline verdict propagation,
runtime policy declarations, operator injection/override handling, and a bridge
for existing state during migration. Otherwise the DSL becomes a thin skin over
opaque handlers instead of the public workflow contract.

Example:

```python
from arnold.workflow import Pipeline, artifact, capability, input, state
from arnold.patterns import agent, branch, critique, fact_check, fanout
from .policy import has_blockers


pipeline = (
    Pipeline("source_grounded_draft", version="1")
    .inputs(
        pitch=input.text(),
        publication_guidelines=input.file(),
    )
    .state(
        review_round=state.int(default=0),
        blocking_issues=state.int(default=0),
    )
    .artifacts(
        outline=artifact.markdown(),
        research_notes=artifact.collection(),
        draft=artifact.markdown(),
        critique_report=artifact.markdown(),
        fact_check_report=artifact.json(),
        final_article=artifact.markdown(),
        provenance_bundle=artifact.json(),
    )
    .capabilities(
        research=capability.web() + capability.read_files(),
        drafting=capability.read_files() + capability.write_artifacts(),
        fact_checking=capability.web() + capability.read_files(),
    )
    .step(
        agent(
            id="outline",
            role="planner",
            prompt=(
                "Turn the pitch and publication guidelines into a sourced "
                "article outline with explicit section goals."
            ),
            inputs={
                "pitch": input.ref("pitch"),
                "guidelines": input.ref("publication_guidelines"),
            },
            writes={"outline": artifact.ref("outline")},
        )
    )
    .step(
        fanout(
            id="research",
            foreach="sections(artifacts.outline)",
            step=agent(
                role="researcher",
                prompt_file="prompts/research_section.md",
                capabilities="research",
                writes={"notes": artifact.ref("research_notes")},
            ),
        )
    )
    .step(
        agent(
            id="draft",
            role="writer",
            prompt_file="prompts/draft_article.md",
            inputs={
                "outline": artifact.ref("outline"),
                "notes": artifact.ref("research_notes"),
            },
            writes={"draft": artifact.ref("draft")},
        )
    )
    .step(
        critique(
            id="critique",
            subject=artifact.ref("draft"),
            lenses=[
                "argument_strength",
                "missing_context",
                "reader_clarity",
                "source_coverage",
            ],
            writes={"report": artifact.ref("critique_report")},
        )
    )
    .step(
        agent(
            id="revise",
            role="writer",
            prompt_file="prompts/revise_article.md",
            inputs={
                "draft": artifact.ref("draft"),
                "critique": artifact.ref("critique_report"),
            },
            writes={"draft": artifact.ref("draft")},
            updates={"review_round": state.ref("review_round") + 1},
        )
    )
    .step(
        branch(
            id="review_gate",
            condition=has_blockers(artifact.ref("critique_report")),
            routes={True: "revise", False: "fact_check"},
        )
    )
    .step(
        fact_check(
            id="fact_check",
            subject=artifact.ref("draft"),
            evidence=artifact.ref("research_notes"),
            capabilities="fact_checking",
            writes={"report": artifact.ref("fact_check_report")},
        )
    )
    .step(
        agent(
            id="finalize",
            role="editor",
            prompt_file="prompts/final_edit.md",
            inputs={
                "draft": artifact.ref("draft"),
                "fact_check": artifact.ref("fact_check_report"),
            },
            writes={"article": artifact.ref("final_article")},
        )
    )
)
```

Prompts are not required to live in markdown files. A package can use inline
strings, prompt builder functions, data files, or markdown files. The only rule
is that the resolved prompt content and prompt provenance are recorded in the
run.

Generated JSON, graph, markdown, or text views may exist for inspection, graph
rendering, or receipts, but they are not edited by hand and are not
authoritative. The canonical pipeline definition is Python.

There should be one canonical representation per pipeline. Do not maintain both
`pipeline.py` and a hand-written declarative spec for the same workflow. If a
view is useful, generate it from Python and treat it as disposable output.

## Pattern Library

Patterns are reusable semantic blocks. They should be rich enough that agents do
not reinvent common workflows, but not so hardwired that they become kernel
assumptions.

There are two kinds of patterns.

### Primitive Patterns

Primitive patterns either express structural control flow or require kernel
guarantees. They should exist early and have direct conformance tests:

- `agent`: one model/tool call with declared inputs, outputs, capabilities;
- `fanout`: run one step across a collection;
- `merge`: combine artifacts with a reducer;
- `branch`: route based on a condition or structured result;
- `loop`: repeat until a condition, budget, or max iteration;
- `human_gate`: durable human decision point;
- `external_call`: fenced side-effect invocation;
- `subpipeline`: invoke another pipeline definition as a child run.

### Composed Patterns

Composed patterns are opinionated wiring over primitives. They are valuable, but
they should graduate into `arnold.patterns` only after repeated use across
multiple pipeline packages:

- `critique`: `agent` plus lens-structured prompt and findings schema;
- `review`: `agent` or `human_gate` plus structured findings;
- `revise`: `agent` wired to prior critique/review input;
- `fact_check`: `agent` plus evidence-anchored verification schema;
- `compare` / `vote` / `jury`: `fanout` plus aggregation strategy;
- `provenance_bundle`: `merge` over event and artifact refs.

Before graduation, composed patterns can live in pipeline packages or an
incubation namespace. Graduation requires at least two non-Megaplan consumers,
stable schema, event behavior, capability requirements, and tests.

A generic critique pattern might look like:

```python
critique(
    id="critique_campaign",
    subject=artifact.ref("campaign_plan"),
    lenses=[
        "audience_fit",
        "budget_risk",
        "channel_overlap",
        "creative_fatigue",
    ],
    merge=weighted_findings,
    routes={"pass": "approve", "issues": "revise_campaign"},
)
```

Megaplan can use the same pattern with Megaplan-specific lenses:

```python
critique(
    id="critique",
    subject=artifact.ref("plan"),
    lenses=[
        "correctness",
        "completeness",
        "execution_risk",
        "evidence_quality",
    ],
    routes={
        "revise": "revise",
        "finalize": "finalize",
        "tiebreaker": "tiebreaker",
    },
)
```

The pattern is shared. The semantics are supplied by the template.

## Certified Execution Backends

The Python workflow DSL compiles to certified execution backends. There should
not be one monolithic executor that tries to become every possible control-flow
model, and there should not be an ungoverned zoo of incompatible adapters.

Backends are implementation infrastructure, not product concepts. Authors should
usually write patterns and routes, not manually think in executor classes.
Operators still need visibility into which backend was selected, what replay
semantics it declares, and what guarantees it has passed.

Likely backends include:

- **DAG**: dependencies, fanout/fanin, incremental recomputation, artifact cache
  validation;
- **state machine**: named states, guarded transitions, cyclic workflows,
  resumable lifecycle;
- **saga**: long-running external side effects, compensation, durable intents;
- **external adapter**: bridge to Temporal, Airflow, CI, cloud batch, or custom
  schedulers while preserving Arnold events/artifacts/capabilities;
- **choreography**: event-driven reactions and monitors, added only when a real
  pipeline needs it.

Every backend must implement the same substrate conformance:

- write Arnold events;
- store Arnold artifacts;
- enforce Arnold capabilities;
- use Arnold human decisions;
- use Arnold side-effect fences;
- emit Arnold cost/provenance records;
- support replay/status to the degree they declare.

The DSL should expose backend choice when it matters:

```python
Pipeline("canary_cortex").execution_backend("saga")
```

but default to compiler selection for ordinary cases. This avoids both extremes:

- no single god-executor;
- no ungoverned zoo of incompatible adapters.

## What Megaplan Owns

Megaplan remains the flagship product/template package. It should own the
planning semantics users actually mean when they say "run a megaplan".

Megaplan owns:

- prep/plan/critique/gate/revise/finalize/execute/review topology;
- chain, epic, milestone, and plan satisfaction semantics;
- tiebreaker behavior;
- completion policy and evidence requirements;
- planning prompts, critique lenses, and review policy;
- profile names and planning slot assignments;
- `.megaplan` artifact layout;
- Megaplan receipts and operator-facing status;
- the `megaplan` CLI;
- cloud/babysitting workflows specific to chains and epics;
- compatibility with existing skills, docs, wrappers, and archived plans.

Megaplan should be impressive because it composes Arnold primitives and patterns,
not because it secretly owns the runtime.

Megaplan's default template might look like:

```python
from arnold.workflow import Pipeline, artifact
from arnold.patterns import agent, branch, critique, revise, subpipeline
from .policy import megaplan_gate
from .prompts import critique_prompt, execute_prompt, finalize_prompt, plan_prompt


pipeline = (
    Pipeline("megaplan_default")
    .step(agent(id="prep", role="researcher"))
    .step(agent(id="plan", role="planner", prompt=plan_prompt))
    .step(
        critique(
            id="critique",
            subject=artifact.ref("plan"),
            prompt=critique_prompt,
            lenses=[
                "correctness",
                "completeness",
                "execution_risk",
                "evidence_quality",
            ],
        )
    )
    .step(
        branch(
            id="gate",
            condition=megaplan_gate(artifact.ref("critique")),
            routes={
                "revise": "revise",
                "finalize": "finalize",
                "tiebreaker": "tiebreaker",
            },
        )
    )
    .step(revise(id="revise"))
    .step(agent(id="finalize", prompt=finalize_prompt))
    .step(subpipeline(id="execute", prompt=execute_prompt))
    .step(
        critique(
            id="review",
            lenses=[
                "implementation_correctness",
                "evidence_sufficiency",
                "residual_risk",
            ],
        )
    )
)
```

Arnold understands the Python DSL and patterns. Megaplan defines
`megaplan_gate`, the lenses, the prompt values/builders, the receipts, the state
schema, and the meaning of completion.

## What Arnold Must Not Own

Arnold must not hardwire:

- Megaplan phase names;
- Megaplan `Profile` slots;
- plan/critique/gate/tiebreaker semantics;
- chain, epic, milestone, or completion-policy vocabulary;
- Megaplan state keys;
- Megaplan receipt layouts;
- `.megaplan` directory assumptions in kernel packages;
- user-facing Megaplan CLI behavior.

These can appear in `arnold_pipelines.megaplan`, compatibility packages, and
templates. They should not appear in `arnold.kernel`, `arnold.agent`, or the
core DSL.

## Compatibility Surfaces

These must survive the migration window:

- `megaplan` console script;
- top-level `import megaplan` and public import surface covered by
  characterization tests;
- existing `.megaplan/plans`, `.megaplan/plans/.chains`, receipts, state files,
  events, routing ledgers, archived plans, and cloud wrappers;
- `ArnoldStoreAdapter` and `ArnoldBlobAdapter` for live Arnold callers;
- `megaplan init --from-arnold-epic` and related Arnold-store workflows;
- skill docs and operator docs that invoke `megaplan`.

Compatibility shims are acceptable only if they are named, owned, tested, and
deletion-gated.

Keep a deletion-gate registry:

```python
CompatShim(
    name="megaplan.compat.imports.AgentSpec",
    owner="arnold-migration",
    introduced="2026-06",
    minimum_release_window=2,
    expiration_trigger=(
        "no import hits in compatibility telemetry for two releases"
    ),
    test_after_expiration="import must fail outside compat allowlist",
)
```

## Migration Plan

### Phase 0: Characterize Current Behavior

Freeze today's behavior before moving architecture. This phase is partly done
on `origin/main`, but it must be refreshed against the actual port base before
any quarry extraction:

- CLI parser snapshots;
- public import surface;
- `.megaplan` artifact layout;
- cloud wrapper scripts and rendered cloud templates;
- skill installation paths and generated skill/AGENTS content;
- pipeline golden outputs;
- resume behavior;
- event/status/trace output;
- cost accounting;
- worker fanout behavior.

This prevents "architecture" from silently changing product behavior.

Also snapshot the compatibility surface that `arnold-generalized-pipeline`
deleted too aggressively: top-level `import megaplan`, the `megaplan` console
script, existing skill paths, and `.megaplan` artifact consumers. If we move
Megaplan to `arnold_pipelines.megaplan`, those surfaces need named shims before
old files disappear.

### Phase 1: Land Safety And Stability Gates

Before extraction, land the gates and stability fixes that protect the current
system. The branch audit found that most stability/config work lives on an
older `09ba01a9` lineage, with
`fix/finalize-readiness-deadturn-and-baseline-cache` as the integration branch.
That branch should not become the Arnold base, but its relevant fixes must be
ported or landed before the Arnold extraction is considered trustworthy.

- parent import-leak ratchet for future Arnold packages;
- engine/target write-isolation regression;
- package-resolution isolation test;
- Hermes and Shannon worker isolation tests;
- process reaping/dead-turn coverage;
- baseline and evidence-window fixes;
- cost single-emission test;
- event-to-state replay divergence measurement;
- side-effect intent/receipt smoke test for one real external path;
- no state mutation outside recorded events for critical paths.

Land-first or cherry-pick-adapt:

- `5bfdca5e`: process-group reaping for session-detached descendants;
- `cb53c5bd`, `0e326b18`, `0c570a2b`, `4706db94`: Shannon/tmux isolation,
  liveness, dead-turn, and baseline-cache hardening;
- `cb2dcceb`: project-scoped config, while ensuring repo-local config cannot
  grant dangerous execution powers by default;
- `41571fcd`: cost/provenance events for Codex-routed execute tasks;
- `4b520bdb`: git-tree-authoritative landed-diff and verify command;
- `f1402945`: evidence-window contamination control.

Defer `mp-test-blast-radius`, `mp-tbr-merge`, and Shannon stream work unless a
specific later Megaplan-package milestone needs them.

### Phase 2: Design The Kernel And DSL Contract Together

Do not freeze the kernel before the DSL abstraction is clear. The kernel exists
to support the public Python DSL and its runtime guarantees. Design these
contracts together:

- `RunEnvelope`;
- artifact refs and blob/store protocol;
- event journal envelope;
- neutral agent request/result contracts;
- capability manifest and policy check protocol;
- cost/usage envelope;
- human decision record;
- side-effect intent/receipt contract;
- `Pipeline`, step, artifact, state, capability, route, and backend-selection
  objects for the Python DSL.

Then add the kernel modules additively without deleting Megaplan paths. Megaplan
can initially re-export or adapt these. The important part is to create one
source of truth without breaking callers.

The newer branches already contain usable kernel ingredients. Port them by
contract, not by namespace:

- use `arnold/runtime/*` event journal, WAL/replay, outcome, recovery, and
  side-effect code as the starting implementation for `arnold.kernel`;
- use cost/media code from `fix/arnold-neutralize-canonicalusage` as the
  starting neutral cost envelope;
- use `arnold/agent/contracts.py` as the starting agent contract, after
  removing any worker-specific fields such as `shannon_plan` from the neutral
  result type;
- use `arnold/conformance/` as the initial import-coupling ratchet, then expand
  it into semantic coupling checks.

Do not let existing `arnold/pipeline` flatten the target layers. Split the
useful pieces into `kernel`, `workflow`, `patterns`, and `execution` as they are
ported.

### Phase 3: Introduce The Python Workflow DSL And Authoring Tools

Define the Python pipeline object model and compiler interface:

- Python DSL representation;
- input/state/artifact/capability declarations;
- expression refs for `inputs.*`, `state.*`, `artifacts.*`, `events.*`;
- validation errors that agents can understand and fix;
- pattern invocation model;
- execution backend selection.

The DSL should be documented with small examples and designed for agents to
author directly. Do not add a hand-authored YAML/config mirror. Generated views
are for inspection only.

Authoring tools are not Phase 9 polish. Add them with the DSL:

- `arnold validate`;
- generated graph/summary view;
- capability diff before execution;
- dry-run execution preview;
- repairable validation errors designed for agents;
- prompt provenance preview.

The existing `PipelineBuilder`, `Stage`, `Edge`, `ParallelStage`, and
`StepResult.next` model can be reused as compiler IR or as a certified graph
backend. It must not be the public Python DSL. The public DSL should stay at the
agent-readable level: inputs, state, artifacts, steps, patterns, capabilities,
routes, and backend choice.

### Phase 4: Build The First Pattern Library

Implement primitive patterns against the kernel:

- `agent`;
- `fanout`;
- `merge`;
- `branch`;
- `loop`;
- `human_gate`;
- `external_call`;
- `subpipeline`.

Each primitive pattern should have:

- a schema;
- examples;
- event emissions;
- artifact behavior;
- capability requirements;
- conformance tests.

Incubate composed patterns such as `critique`, `review`, `revise`,
`fact_check`, `jury`, and `provenance_bundle` in pipeline packages first. Move
them into `arnold.patterns` only after repeated non-Megaplan use proves the
interface.

For Megaplan specifically, do not graduate current monolithic handler wrappers
as composed patterns. A composed pattern must be expressible as wiring over
primitives, with explicit inputs, outputs, events, and routing.

Quarry candidates:

- direct: `pattern_select`, `pattern_stops`, `pattern_joins`,
  `pattern_dynamic`, and subpipeline helpers where they are policy-neutral;
- reshape: Megaplan critique/revise/gate topology helpers by parameterizing
  labels and policies rather than baking in `proceed`, `iterate`,
  `tiebreaker`, or `escalate`;
- reject as generic patterns: any helper that requires Megaplan phase names,
  `PlanState`, profile slots, or gate recommendation literals.

### Phase 5: Certify Execution Backends

Start with two or three backends, not every possible shape:

- DAG;
- state machine;
- saga.

Each backend must pass adapter certification:

- causal event ordering;
- artifact writes through Arnold store;
- capability enforcement;
- human decision suspension/resume;
- side-effect fencing;
- cost/provenance records;
- declared replay semantics.

Choreography and external adapters can follow once the substrate is proven.

The existing branch executor should be treated as the initial DAG/state-machine
backend candidate. Its hook protocol and walk-loop are useful, but the backend
must pass certification without promoting executor internals into the public
DSL.

### Phase 6: Prove A Serious Non-Megaplan Pipeline

Do not use a toy demo. Use a pipeline that stresses the abstractions:

- source-grounded draft;
- legal diligence;
- iterated jury;
- canary rollout;
- scientific robustness audit.

It must use:

- agent dispatch;
- artifacts;
- event replay;
- human decision;
- at least one reusable pattern;
- at least one non-trivial route;
- capability enforcement;
- cost/provenance records;
- no imports from `megaplan.*`.

This is the proof that Arnold is not just Megaplan with renamed nouns. Treat it
as a make-or-break gate. Do not port Megaplan onto Arnold until this succeeds.

The newer branches partially satisfy this with `arnold/pipelines/deliberation`
and `arnold/pipelines/evidence_pack`. Use them as quarry, but rerun the proof
after the layer split: passing "no Megaplan imports" is not enough if the proof
still depends on the old flat `arnold.pipeline` surface or graph-builder public
API.

### Phase 7: Port Megaplan Onto The DSL And Patterns

Represent Megaplan's default pipeline as a Python template over Arnold's DSL:

- Megaplan supplies prompt values, builders, or files;
- Megaplan supplies state schemas;
- Megaplan supplies critique lenses;
- Megaplan supplies gate functions;
- Megaplan supplies receipts;
- Megaplan supplies CLI compatibility;
- Arnold supplies runs, artifacts, events, capabilities, human gates,
  side-effect fences, agent contracts, and pattern execution.

Keep compatibility shims during this phase.

This phase also has to retire Megaplan-shaped runtime assumptions:

- fixed `GateRecommendation` literals in generic types;
- `Step.kind` values such as `judge` and `decide` as runtime primitives;
- executor branches that know Megaplan gate semantics;
- direct stage imports of `megaplan.handle_*`;
- direct `PlanState` assumptions in generic context objects.

The current generalized branch goes too far by deleting the top-level
`megaplan/` package before the compatibility shims are ready. Restore or retain
that surface during the strangler window. The final target can move Megaplan
implementation to `arnold_pipelines.megaplan`, but `import megaplan`, the
console script, skills, and artifact layout must remain covered by explicit
compatibility tests and deletion gates.

Namespace migration order:

1. Keep `arnold.pipelines.megaplan` working while introducing
   `arnold_pipelines.megaplan` as the real implementation package.
2. Convert `arnold.pipelines.megaplan` into a named compatibility shim.
3. Keep top-level `megaplan` as the product CLI/import surface unless and until
   compatibility telemetry proves it can be retired.
4. Run conformance against all three names so the gate does not pass merely
   because a package moved.

### Phase 8: Collapse Duplicates

Only after both a non-Megaplan pipeline and Megaplan itself run through Arnold:

- delete duplicate cost/accounting types;
- delete duplicate agent contracts;
- delete duplicate receipt write primitives;
- delete duplicate event envelopes;
- collapse worker fanout adapters where safe;
- remove any second executor that is not a certified orchestrator;
- move stale types behind explicit compat shims or delete them.

Also collapse the specific duplication discovered in the quarry audit:

- `arnold/pipelines/megaplan/_pipeline/*` copies of generic pattern/executor
  modules;
- `arnold/agent/*` versus `arnold/pipelines/megaplan/agent/*`;
- token/media pricing shims that duplicate neutral `CostResult` and
  `CanonicalUsage`;
- `hermes_cli` and `honcho_integration` relocation shims once callers have
  moved.

Do not delete compatibility shims solely because tests pass. Require telemetry
or other concrete evidence that old import/CLI/artifact paths are no longer in
use across a release window.

### Phase 9: Polish Authoring Workflows

The end-user payoff is that agents can build pipelines quickly. By this phase,
the core authoring loop should already exist; now harden it with:

- `arnold new pipeline` from natural-language brief;
- pattern catalog docs;
- examples for common workflows;
- template registry;
- replay/status viewer.

The goal is that an agent can author a useful pipeline module in minutes, run a
dry validation, and then execute it under Arnold guarantees.

## First Gates To Add

- Parent import-leak gate: kernel/agent/workflow packages cannot import
  Megaplan.
- Semantic-coupling gate: kernel/agent/workflow/pattern packages cannot contain
  Megaplan phase names, `PlanState`, `.megaplan`, profile slots, handler names,
  or gate/tiebreaker literals except in named compatibility allowlists.
- Package-name staleness gate: import and semantic-coupling checks must know
  all active Megaplan package names (`megaplan`, `arnold.pipelines.megaplan`,
  and `arnold_pipelines.megaplan`) so a rename cannot make the gate report a
  false clean result.
- Layering gate: public authoring DSL cannot expose `Stage`, `Edge`,
  `StepResult.next`, executor branches, or Megaplan package internals as the
  required authoring API.
- Never-port artifact gate: extraction branches fail if they include
  `.megaplan/_archived-plans/**`, `.hermes_state/**`, DB/WAL/SHM files, prompt
  dumps, runtime state, receipts, or driver logs.
- Engine/target write-isolation regression.
- Package-resolution isolation regression.
- Worker cwd/symlink/editable-install isolation regression.
- Capability-denial tests for undeclared key/shell/file/network/fanout access.
- Event replay test reconstructing a full run timeline from one artifact root.
- Event-to-state replay divergence test for current Megaplan plans.
- Human decision audit test: decision injection requires authenticated identity
  and emits an immutable event.
- Side-effect fence test: crash after intent does not duplicate external call.
- Side-effect fence pilot for one real path, preferably chain git push or cloud
  notification.
- Artifact lifecycle test: downstream agent can read an upstream artifact after
  producer process cleanup.
- Cost/accounting single-emission test during transition.
- Python DSL conformance tests with repairable validation errors.
- Pattern conformance tests for `agent`, `fanout`, `critique`, `branch`,
  `human_gate`, and `external_call`.
- Orchestrator certification tests.
- CLI/import compatibility test for the `megaplan` shim.
- Cloud wrapper, skill output, event/trace/status, and `.megaplan` layout
  characterization snapshots.
- Store adapter contract test for live Arnold callers.

## What Not To Do

- Do not merge `arnold-generalized-pipeline` wholesale.
- Do not delete the top-level `megaplan` package or console script before named
  compatibility shims and deletion telemetry exist.
- Do not make `PipelineBuilder`, `Stage`, `Edge`, or `StepResult.next` the
  public agent-facing workflow DSL. They can be IR or backend machinery.
- Do not make one Megaplan-shaped executor the universal Arnold runtime.
- Do not make one bloated `StepContext` carry every possible pipeline's domain
  needs.
- Do not call a deterministic toy proof pipeline sufficient.
- Do not make "critique" a kernel assumption with Megaplan semantics.
- Do not accept "no Megaplan imports" as proof of neutrality. Semantic coupling
  through phase names, gate labels, state keys, and profile slots is still
  coupling.
- Do not leave human decisions, idempotency, event ordering, or artifact
  lifecycle to every pipeline package.
- Do not let repo-local config grant dangerous execution powers by default.
- Do not let compatibility shims become nameless permanent infrastructure.
- Do not import generated run artifacts, archived plans, prompts, session DBs,
  or runtime ledgers into source history as part of the port.
- Do not pre-register heavy worker adapters at import time. Codex/Shannon/Hermes
  adapters should be caller-injected or lazily loaded so importing
  `arnold.agent` stays neutral.

## Branch Retirement Criteria

Old branches become safe to delete only after their useful content has been
classified and either landed, reshaped into the new plan, or explicitly
discarded.

| Branch Or Worktree | Retire After |
| --- | --- |
| `arnold-generalized-pipeline` | Runtime/event/cost/agent/conformance/non-Megaplan proof work has landed or been rejected, local-only commits are handled, and no generated artifacts are part of the clean branch. |
| `origin/arnold-generalized-pipeline` | Same as local branch, plus local `b1ed2225`, `4544c94d`, `5ea1f70a`, and merge commits have been reconciled. |
| `arnold/panel-dispatch` | Unique Codex/Shannon adapters, `free_text` worker support, and tests are ported or intentionally rejected. |
| `fix/arnold-conformance-gate` | `arnold/conformance/` and stricter semantic/layering gates have landed on the clean base. |
| `fix/arnold-neutralize-canonicalusage` | Neutral cost/media/token accounting has landed and Megaplan pricing shims are named. |
| `arnold-epic` | Already an ancestor of `origin/main`; safe to retire after confirming no unpushed local-only commits or stashes depend on it. |
| `fix/finalize-readiness-deadturn-and-baseline-cache` | Stability/config fixes and current plan docs are landed or intentionally abandoned; it should not be used as the Arnold base. |
| `fix/engine-bug-ledger` | Commit `41571fcd` is ported or rejected. |
| `feat/git-tree-authority` | Git-tree authority/evidence verification primitives are ported or assigned to a later evidence milestone. |
| `mp-milestone-attribution-ground-truth` | Evidence-window contamination control is ported or assigned to a later evidence milestone. |
| `mp-test-blast-radius`, `mp-tbr-merge` | Test-selection work is either moved to a Megaplan-package hardening milestone or intentionally discarded. |
| Shannon stream branches | Explicitly out of Arnold substrate scope unless a worker milestone adopts them. |

## Load-Bearing Questions

These are the questions that should keep steering the migration:

1. **Is this concept a hard runtime guarantee or a domain semantic?**
   Hard guarantees belong in Arnold kernel. Domain semantics belong in patterns,
   templates, or pipeline packages.

2. **Can an agent author this workflow using the public Python DSL?**
   If not, the DSL and pattern docs are not concrete enough.

3. **Would 100 pipelines all need this exact behavior?**
   If yes, consider kernel or a certified pattern. If no, keep it out of core.

4. **Does this belong in a pattern rather than the kernel?**
   `critique`, `review`, `judge`, `revise`, and `fact_check` are reusable, but
   their meanings vary by domain.

5. **Can a non-Megaplan pipeline use this without importing Megaplan?**
   If not, Arnold is not yet real.

6. **Can an operator replay and audit this after a crash or human pause?**
   If not, the substrate is too weak.

7. **Can an external side effect be retried without duplication?**
   If not, the system is unsafe for money, deployments, notifications, and
   production APIs.

8. **Can the compatibility shim be deleted deliberately?**
   If not, it is becoming permanent architecture.

9. **Is this runtime behavior actually generic, or just Megaplan semantics with
   neutral names?**
   Fixed gate recommendations, tiebreaker assumptions, phase names, profile
   slots, and `PlanState` fields are warning signs.

10. **Does the DSL expose the production behavior that matters?**
    Multi-way typed dispatch, runtime policy, operator injection, subpipeline
    verdict propagation, and migration-state bridges must not disappear into
    opaque handler code.

## Final Target

The final target is a system where an agent can write:

```python
from arnold.workflow import Pipeline, artifact
from arnold.patterns import agent, branch, critique, fanout, merge, revise
from .policy import is_converged


pipeline = (
    Pipeline("iterated_jury_plan")
    .step(agent(id="draft_plan", prompt=build_initial_plan_prompt))
    .step(
        fanout(
            id="critic_round",
            foreach=[
                "correctness",
                "implementation_risk",
                "testing",
                "cost",
                "operator_workflow",
                "simplifier",
            ],
            step=critique(
                subject=artifact.ref("current_plan"),
                prompt=critic_prompt,
            ),
        )
    )
    .step(merge(id="merge", reducer=merge_critic_reports))
    .step(revise(id="revise", prompt=revision_prompt))
    .step(
        branch(
            id="decide",
            condition=is_converged(artifact.ref("merged_report")),
            routes={False: "critic_round", True: "finalize"},
        )
    )
    .step(agent(id="finalize", prompt=finalize_prompt))
)
```

And Arnold can:

- validate it;
- show required capabilities;
- run it locally or remotely;
- dispatch agents;
- persist artifacts;
- emit replayable events;
- suspend for humans;
- avoid duplicated side effects;
- track cost and provenance;
- let Megaplan or another product package add domain-specific meaning.

That is the elegant endpoint: concrete enough for agents to build with quickly,
strict enough for operators to trust, and layered enough that Megaplan can be a
flagship product without becoming the hidden architecture of every future
pipeline.
