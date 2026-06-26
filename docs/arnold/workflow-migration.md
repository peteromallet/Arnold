# Workflow Migration

## M6 Clean-Break Completion

M6 finalized the clean break from legacy public surfaces. The following surfaces
were removed from the source tree and will not resolve at import time:

| Deleted surface | Migration target |
| --- | --- |
| `arnold.pipelines.megaplan` (and sibling `arnold.pipelines.*` packages) | `arnold_pipelines.megaplan` for product-specific shipped pipelines; `arnold.workflow` for neutral authoring. |
| `arnold.pipeline` public builder/executor symbols (`PipelineBuilder`, `Stage`, `Edge`, `ParallelStage`, `run_pipeline`) | `arnold.workflow.dsl.Pipeline`, `arnold.workflow.dsl.Step`, `arnold.workflow.dsl.Route`; execution via `arnold.execution.run`. |
| `arnold pipelines *` CLI subcommands | `arnold workflow {check,manifest,dot,dry-run,run,resume,describe}`. |
| `arnold <module> *` step commands (`init`, `plan`, `prep`, ...) | `arnold_pipelines.megaplan` package-local CLI (`python -m arnold_pipelines.megaplan ...`) or `arnold workflow run`. |
| `arnold/agent/*` vendored Hermes tool shims delegated to `arnold.pipelines.megaplan.agent.tools.*` | Native `arnold.agent.tools.*` stubs (M6) or product-specific tool implementations in `arnold_pipelines.megaplan`. |
| Root-level `test_*.py` files importing deleted surfaces | Removed; current tests live under `tests/arnold/`, `tests/arnold_pipelines/`, `tests/cli/`, `tests/installed_wheel/`. |

Canonical authoring and runtime paths after M6:

- Author workflows with `arnold.workflow.dsl` and `arnold.workflow.compiler`.
- Compile and validate with `arnold workflow check --module <module>:build_pipeline`.
- Run with `arnold workflow run` or `arnold.execution.run`.
- Ship product pipelines under `arnold_pipelines.<product>` with `manifest_hash`
  registered in `pipeline_ids.json`.

Any code still importing `arnold.pipelines.megaplan` must be migrated before it
can run against the M6 tree; those imports raise `ModuleNotFoundError`.

## M1 Baseline Evidence

Batch 1 verified that the M1 implementation branch descends from `origin/main` and does not include a merge from `native-python-pipelines`.

- Current branch: `workflow-manifest-runtime-m1-baseline`
- `HEAD`: `228b675d` (`megaplan: m1-baseline-guardrails-and-20260621-2355 init`)
- `origin/main`: `06b6e8fa` (`fix(megaplan): anchor engine root for chain worktree isolation`)
- Merge base: `06b6e8fa1e05`
- Ancestry check: `git merge-base --is-ancestor origin/main HEAD` returned exit code `0`
- Baseline diff check: `git diff --stat origin/main...HEAD` produced no file changes
- Merge audit: `git log --merges --oneline origin/main..HEAD` produced no merge commits
- Local native branch check: `git merge-base --is-ancestor native-python-pipelines HEAD` returned exit code `1`
- Remote native branch check: `git merge-base --is-ancestor origin/native-python-pipelines HEAD` returned exit code `1`

Because ancestry was already valid, no branch repair was performed. The `native-python-pipelines` local and remote branches exist separately, but neither is contained in `HEAD` and neither was merged into the M1 branch.

## Mainline Quarry Inventory

M1 treats current mainline behavior as evidence. The files below are inventoried for contract design, but this milestone must not modify `arnold.runtime`, `arnold.pipeline`, or `arnold.pipelines.megaplan` runtime behavior while introducing `arnold.workflow` and `arnold.kernel` contracts.

| Current artifact or primitive | Current role | M1 disposition | Contract target or handling |
| --- | --- | --- | --- |
| `tests/fixtures/golden/pipeline_fresh_run.json` | Characterization fixture for a fresh planning run. | Retained | Keep as a behavioral baseline fixture. Later workflow fixture normalization may reference it, but M1 should not rewrite it for migration convenience. |
| `tests/fixtures/golden/pipeline_iterate.json` | Characterization fixture for an iterative/gate path. | Retained | Keep as a behavioral baseline fixture. Any future normalized workflow copy needs an explicit explanation artifact if behavior changes. |
| `tests/fixtures/golden/pipeline_resume_after_finalize.json` | Characterization fixture for resume after finalize behavior. | Retained | Keep as a behavioral baseline fixture and use it as evidence for replay/resume contract coverage. |
| `arnold/pipeline/discovery/manifest.py` `Manifest` and `read_manifest()` | Import-free package discovery reader for module-level pipeline metadata, required fields, `SKILL.md` sibling validation, API-version validation, and package manifest hashing. | Re-chartered | Quarry evidence for `arnold.workflow.WorkflowManifest` identity and validation semantics. Existing package-discovery behavior remains intact; new workflow manifest hashing should be neutral and deterministic rather than a bridge around this reader. |
| `arnold/pipeline/discovery/manifest.py` `ARNOLD_IDENTITY_SCHEMA` and `_manifest_hash()` | Current discovery hash anchors package metadata, module source hash, skill doc hash, and schema identity. | Superseded for workflow manifests | `WorkflowManifest.manifest_hash` becomes the canonical runtime coordinate for workflow contracts. The existing discovery hash remains package-discovery evidence and must not be repurposed as the workflow hash. |
| `arnold/pipeline/discovery/judge_manifest.py` `JudgePieceManifest`, `JudgeManifestPort`, `compute_piece_version()`, and `compute_judge_version()` | Import-free sidecar identity for judge pieces, rubric/model identity, typed ports, and deterministic piece/judge hashes. | Retained | Judge manifests survive M1 as independent sidecar artifacts. Cross-reference them to workflow manifests by `WorkflowManifest.manifest_hash` plus `piece_version` and `judge_version`; do not absorb judge manifests into the workflow manifest contract in M1. |
| `arnold/pipeline/discovery/trust.py` `TrustGrade.AUTO_EXEC` | Path-derived in-tree trust classification that auto-executes when a module is under the caller-provided in-tree fragment. | Re-chartered | Quarry evidence for explicit kernel trust and dispatch identity anchors. Workflow/kernel contracts should name the trust anchor, not infer it from user manifest metadata. |
| `arnold/pipeline/discovery/trust.py` `TrustGrade.QUARANTINED` | Path-derived out-of-tree/user-home classification requiring explicit promotion before execution. | Re-chartered | Quarry evidence for kernel suspension/quarantine state and replay quarantine records. Keep the existing discovery classifier intact. |
| `arnold/pipeline/discovery/trust.py` `TrustGrade.BLESSED` and `BLESSED_ALLOWLIST` | Explicit allowlist promotion that can auto-execute from either origin. | Re-chartered | Quarry evidence for future capability/trust policy inputs. M1 contracts should carry the identity anchor and state label without implementing a policy engine. |
| `arnold/pipeline/discovery/trust.py` `derive_tenant_id()` | Stable SDK-derived tenant id from CLI name plus resolved module path. | Re-chartered | Quarry evidence for kernel identity derivation. New kernel IDs should be explicit structured values; the old helper remains available for discovery callers. |
| `arnold/pipeline/schema_registry.py` `ContractSchemaRegistry`, `schema_version_for()`, and accepted-version ranges | File-backed, content-addressed registry for payload schemas and logical-type histories. | Re-chartered | Quarry evidence for `arnold.kernel.content_types` and event payload schema hashes. Retain existing registry behavior while new contracts define neutral content type and schema hash carriers. |
| `arnold/pipeline/pipeline_id_registry.py` `PipelineIdRegistry` and loaders | Source-controlled pipeline identity validation for names, stable IDs, seam IDs, and previous stable IDs. | Re-chartered | Quarry evidence for canonical pipeline/workflow identity derivation. Future runtime coordinates derive from human alias plus `manifest_hash`; the existing registry remains package identity evidence. |
| `arnold/pipelines/megaplan/_pipeline/pipeline_ids.json` and `arnold/pipelines/evidence_pack/pipeline_ids.json` | Product/package registry data consumed by the identity registry validator. | Retained | Keep as source-controlled package registry inputs. Do not move or delete during M1. |
| `arnold/runtime/envelope.py` `RunEnvelope` | Runtime-owned cross-cutting carrier with taint, cost, lineage, deadline, cancellation, retry budget, lease/fencing, capacity grants, and semilattice join behavior. | Re-chartered | Quarry evidence for `arnold.kernel.governor`, control projections, and runtime overlay fields. Existing runtime envelope behavior remains unchanged. |
| `arnold/runtime/envelope.py` `RuntimeEnvelope` | Run-level carrier for plugin identity, manifest hash, schema versions, run id, artifact root, resume cursor, trust/quarantine state, and composed `RunEnvelope`. | Re-chartered | Quarry evidence for kernel run lineage and manifest references. New contracts should expose structured lineage fields rather than importing this runtime module. |
| `arnold/runtime/effect.py` `Effect`, `ReplayClass`, and `NONCOMPENSABLE` | Typed descriptor for replay classes, external-act idempotency keys, compensation, provenance, and effect taint. | Re-chartered | Quarry evidence for `arnold.kernel.effect` and `arnold.kernel.effect_ledger` contracts. M1 should define idempotency and ledger contracts without enforcing old runtime behavior. |
| `arnold/runtime/event_journal.py` `EventEnvelope`, `EventSink`, `NdjsonEventJournal`, and `read_event_journal()` | Store-less NDJSON journal with monotonic sequence sidecars, timestamps, opaque event kinds, payloads, scopes, phases, and idempotency keys. | Re-chartered | Quarry evidence for `arnold.kernel.events` and `arnold.kernel.journal`. New event contracts should carry `manifest_hash`, original manifest refs, payload schema hash, and replay refs without changing this journal. |
| `arnold/runtime/resume.py` `ResumeCursorRef`, `TrustTransition`, and `migrate_legacy_resume()` | Opaque resume cursor and pure legacy-state migration contract with trusted/quarantined manifest mismatch outcomes. | Re-chartered | Quarry evidence for `arnold.kernel.suspension`, reentry IDs, and replay quarantine protocol. Existing resume migration remains intact. |
| `arnold/runtime/semantic_replay.py` `semantic_equivalent()` and `semantic_replay_journal()` | Structural replay comparison and journal folding helper for expected-plan equivalence. | Re-chartered | Quarry evidence for `arnold.kernel.replay` resolver decisions. M1 should define replay resolution/quarantine contracts, not implement a new runner or alter semantic replay. |
| Runtime/package quarry code under `arnold/runtime`, `arnold/pipeline`, and `arnold/pipelines.megaplan` | Existing behavior and product-specific implementation surfaces. | Deleted from M1 contract surface only | No source deletion in M1. These modules are not part of the new neutral `arnold.workflow`/`arnold.kernel` contract surface and should not be imported by it except through explicit future migration work. |

Disposition vocabulary: **retained** means the artifact remains authoritative for current behavior; **superseded** means a new contract will own that role for workflow/kernel surfaces while the old code continues serving current callers; **re-chartered** means the artifact becomes quarry evidence for a neutral contract with no behavior change; **deleted** means excluded from the M1 contract surface only, not removed from the repository.

## Decision Packet Summary

This section consolidates the surviving `/tmp/workflow_decision_docs/*.md` packet so this migration record remains useful after `/tmp` is cleaned. If those temporary files are unavailable, the settled decisions below are the authoritative M1 summary.

The packet contained one real disagreement: one branch recommendation argued for `native-python-pipelines` because it had already crossed a large filesystem deletion boundary, while `base_branch_analysis.md`, `migration_plan_gpt55.md`, the approved M1 gate, and the current branch evidence select `origin/main`. M1 follows the approved gate:

- Build M1 from `origin/main`.
- Do not merge `native-python-pipelines`.
- Treat `native-python-pipelines` and adjacent branches as quarry for tests, bug fixes, runtime lessons, source-span diagnostics, resume/cursor lessons, and golden/parity strategy.
- Port only explicitly selected fixes or lessons after they are reframed around workflow manifests and kernel events.

The architectural decision is also settled: the durable contract is an explicit workflow manifest, not a live native Python program. Authoring may later use a Python data DSL such as `workflow.Pipeline(..., steps=[agent(...), branch(...), loop(...), human_gate(...)])`, but runtime, replay, inspection, and migration are keyed by a serialized manifest with stable node IDs, refs, routes, capabilities, budgets, artifact declarations, topology hash, and `manifest_hash`.

## Rejected Native-First Architecture

The `native-python-pipelines` branch is useful evidence, but its public spine is rejected for the manifest migration:

| Native-first surface | Why it is rejected for the final contract | What M1 does instead |
| --- | --- | --- |
| `@pipeline`, `@phase`, `@decision`, `parallel(...)`, and generator-style workflow bodies | They make Python control flow look like durable runtime state and force Arnold to maintain a permanent restricted-Python compiler as the canonical authoring model. | M1 freezes neutral manifest and kernel contracts first. Restricted/native syntax can only return later as optional private lowering sugar once manifest parity is proven. |
| `NativeProgram`, program counters, native checkpoint cursors, and native dispatch | They bind resume/replay to compiler internals rather than manifest coordinates. | M1 uses `WorkflowManifest.manifest_hash`, topology hashes, `reentry_id`, scope stacks, artifact hashes, and event sequence references as contract coordinates. |
| Graph projection as the final inspection model | It preserves `Stage`/`Edge` vocabulary as a public shape even when the desired runtime contract is a manifest. | M1 records topology through workflow manifest nodes/edges and kernel event/replay contracts. |
| Package-local Megaplan runner hooks such as native runners or bridge dispatch | They keep product-specific dispatch policy inside a private runner path. | M1 separates neutral kernel contracts from product ownership. Later milestones may port Megaplan policy into package-owned hooks around a canonical execution substrate. |
| Moving deleted `_pipeline` code up into `arnold/pipelines/megaplan/*` | It is a relocation, not a clean split; the old surface can be accidentally reintroduced. | M1 does not move or delete the existing product package. It documents quarry evidence and adds neutral contracts in new packages. |

The rejection is not a claim that native work was wasted. The useful pieces are diagnostics, test cases, route/resume edge cases, graph stability lessons, and operational fixes. The rejected part is making native generator/decorator execution the public or runtime source of truth.

## Clean-Break End State

The long-term end state is a clean Arnold/Megaplan split. M1 does not implement that full split, but all M1 contract choices must be compatible with it.

Clean-break means:

- No permanent top-level `megaplan` package or `megaplan` console entrypoint.
- No permanent `_pipeline` tree, compatibility re-export module, bridge allowlist, or package-local graph runner as the public execution path.
- No public `Stage`, `Edge`, `ParallelStage`, `PipelineBuilder`, `Pipeline.builder()`, or `run_pipeline` authoring API for product pipelines.
- Product pipelines ultimately live under product-owned packages such as `arnold_pipelines.megaplan`, while neutral mechanisms live under `arnold.kernel`, `arnold.workflow`, `arnold.agent`, `arnold.execution`, and `arnold.conformance`.
- Existing behavior is preserved by characterization fixtures, golden outputs, event/replay checks, and explicit migration/quarantine records, not by permanent compatibility shims.

The end state still needs an executor. "No graph runtime" means no old public/package-local graph runner contract, not no execution backend. A future `arnold.execution` backend may internally use DAG, state-machine, saga, or choreography machinery, but the public coordinate remains the workflow manifest and kernel event/artifact contracts.

M1 therefore has a deliberately narrower scope: add additive `arnold.workflow` and `arnold.kernel` contracts; do not create a DSL runner; do not move packages; do not delete legacy code; do not add bridge shims.

## Milestone Handoffs

The decision packet described a broader migration, but M1 only freezes the baseline guardrails and manifest/kernel contract. Handoffs from this doc are:

| Milestone | Handoff from M1 | Must not be assumed complete after M1 |
| --- | --- | --- |
| M1 baseline guardrails and contract freeze | Branch decision, quarry inventory, workflow manifest dataclasses, kernel identity/event/artifact/effect/replay contracts, import-boundary guardrails, golden-regression scaffolding, wheel-smoke scaffolding. | No production runner, no DSL compiler, no Megaplan package move, no compatibility deletion. |
| Workflow authoring milestone | Use `WorkflowManifest` as the oracle for any Python data DSL, builder sugar, or optional restricted/native lowering. | Do not let authoring APIs become the runtime identity. Manifest serialization and hash stability remain authoritative. |
| Execution substrate milestone | Build `arnold.execution` around manifest input, kernel events, artifact contracts, capability checks, side-effect fences, suspension, replay, and deterministic test backends. | Do not expose old `Stage`/`Edge` graph APIs as the new public runner. |
| Non-Megaplan proof milestone | Prove at least one serious non-Megaplan workflow through the new DSL/substrate before Megaplan becomes the canonical consumer. Evidence-pack or folder-audit are preferred because they stress human suspension, fanout/reduce, artifacts, and capability enforcement. | A toy linear workflow is not enough to prove neutrality. |
| Megaplan port milestone | Express Megaplan topology through workflow/pattern values, keep prompts/policies/receipts/profile semantics product-owned, and compare against M1 golden behavior. | Do not carry over package-local graph execution or bridge allowlists as final architecture. |
| Clean-break deletion milestone | Delete or fail builds on resurrected legacy surfaces only after equivalent behavior is proven through contracts, fixtures, and conformance checks. | Do not delete behavior just because a path is architecturally obsolete. |

## Discovery, Trust, And Identity Map

The old discovery surfaces remain current-main behavior while workflow
manifests become the runtime identity contract.

| Current primitive | Disposition | Identity anchor after M1 |
| --- | --- | --- |
| Package discovery manifest fields in `arnold/pipeline/discovery/manifest.py` | Retained as package metadata, not runtime workflow manifests. | Regenerated or validated from package metadata; runtime joins use `WorkflowManifest.id + manifest_hash`. |
| `JudgePieceManifest`, `JudgeManifestPort`, `compute_piece_version()`, `compute_judge_version()` | Retained as sidecar judge artifacts. | Judge sidecars keep `piece_version`, `judge_version`, and `rubric_hash`; workflow manifests cross-reference them with `arnold.kernel.ids.JudgeManifestCrossReference` carrying `manifest_hash`, `piece_version`, `judge_version`, `rubric_hash`, and relationship enum. |
| `TrustGrade.AUTO_EXEC` / `auto-executable` | Re-chartered as a trust classification input. | Anchored to the workflow `manifest_hash`; any judge-derived auto-exec decision must name the supporting `JudgeManifestCrossReference` rather than relying on path-derived package identity. |
| `TrustGrade.QUARANTINED` / `quarantined` | Re-chartered as replay/suspension quarantine vocabulary. | Anchored to the mismatched original/observed workflow `manifest_hash` pair, with operator-visible rationale; judge-side quarantine evidence is linked through `JudgeManifestCrossReference` when a judge sidecar participated. |
| `TrustGrade.BLESSED` / `blessed` | Re-chartered as an explicit promotion classification. | Anchored to the promoted workflow `manifest_hash` plus the exact `JudgeManifestCrossReference` or package promotion record that justified promotion. |
| `schema_registry.py` logical types and schema histories | Re-chartered. | Kernel content types carry `type_id`, `schema_version`, `schema_hash`, retention policy, and provenance parent links. |
| `derive_tenant_id()` | Re-chartered. | Runtime identities derive from human alias plus `manifest_hash`; tenant derivation remains package-discovery evidence until a later identity migration. |
| `PipelineIdRegistry` and source-controlled pipeline IDs | Re-chartered. | `Pipeline.id` remains the stable human alias; `manifest_hash` is the runtime discriminator. `Pipeline.version` is authoring metadata unless explicitly promoted by a future amendment. |

Judge manifests survive as independent sidecars in M1 rather than being
absorbed into `WorkflowManifest`. The sidecar boundary is intentional: a judge
piece can have its own piece/rubric/model lineage, while the workflow manifest
owns run topology and runtime replay coordinates. The durable join between
those identities is `arnold.kernel.ids.JudgeManifestCrossReference`, not an
implicit trust row or path-derived package relationship.

## Golden Guardrails

M1 adds normalized workflow fixture summaries under
`tests/fixtures/golden/workflow_manifest_runtime/` and records the normalization
rules in `tests/fixtures/workflow/README.md`. Existing behavioral goldens under
`tests/fixtures/golden/pipeline_*.json` are not rewritten. Import/package-only
moves cannot update those behavioral goldens; any legitimate behavior change
needs a sibling `.explanation.md` artifact that names the behavioral reason.

## Manifest Amendment Protocol

Contract changes after M1 must follow
`docs/arnold/workflow-manifest-amendments.md`. The short rule is: state whether
`manifest_hash` or `topology_hash` changes, state how in-flight runs replay or
quarantine, and add tests for any new volatile fixture normalization.

## Dispatch Ownership

M1 distinguishes neutral dispatch mechanisms from product policy. Ownership is:

| Concern | Arnold substrate owner | Product package owner | M1 contract implication |
| --- | --- | --- | --- |
| Run identity and manifest references | `arnold.workflow`, `arnold.kernel.identity`, `arnold.kernel.events` | Supplies product pipeline id/version and manifest refs. | Kernel records `manifest_hash`, original manifest refs, run IDs, and replay coordinates without importing Megaplan. |
| Agent request/result shape and adapter dispatch | Neutral `arnold.agent`/future execution substrate | Chooses product roles, prompts, profile slots, model policy, and package adapter registration. | M1 kernel contracts must not encode Shannon/Megaplan-only fields as required neutral fields. |
| Capability checks | `arnold.kernel.capability` and future execution guard | Declares product capabilities and policy defaults. | Contracts carry capability identity and check results; policy engines are out of scope for M1. |
| Artifacts and content types | `arnold.kernel.artifact`, `arnold.kernel.content_types` | Chooses product artifact layout, receipts, prompt outputs, and `.megaplan` conventions while they exist. | M1 defines deterministic artifact identity, roots, provenance, and retention pins without freezing Megaplan layout. |
| Events, journal, replay, and quarantine | `arnold.kernel.events`, `arnold.kernel.journal`, `arnold.kernel.replay`, `arnold.kernel.suspension` | Supplies product-specific route labels, resume schemas, and migration alias decisions. | Manifest mismatch resolves by explicit alias or quarantine, not guessing from old Python/graph state. |
| External effects and idempotency | `arnold.kernel.effect` and effect ledger | Declares which product operations are effectful and how compensation/receipts are interpreted. | M1 records intent/fulfillment/receipt/compensation contracts; it does not execute effects. |
| Megaplan topology | None; Arnold only supplies neutral primitives. | Owns prep, plan, critique, gate, revise, tiebreaker, human, finalize, execute, review, chain/epic semantics, lenses, and prompts. | Neutral contracts must not contain Megaplan route vocabulary such as `judge`, `decide`, `tiebreaker`, or `PlanState` except as product payload data. |
| Package discovery and trust | Existing `arnold.pipeline.discovery` remains current behavior; future neutral identity/trust contracts may be derived from it. | Product packages provide package metadata and sidecar judge manifests. | M1 keeps discovery and judge manifests intact; workflow manifests cross-reference judge sidecars rather than absorbing them. |

## Material Summarized From `/tmp/workflow_decision_docs`

The temporary decision packet is summarized as follows:

- `base_branch_analysis.md`: choose `origin/main`; preserve selected fixes and tests from native/friction branches; do not merge native wholesale.
- `gpt55_workflow_choice.md` and `text_workflow_representations.md`: use explicit-node, manifest-shaped Python as the canonical authoring direction; generated YAML/DOT/Markdown are views, not hand-maintained sources.
- `migration_plan_gpt55.md`: start from `origin/main`, create workflow/kernel contracts first, then DSL, runner, package layout, Megaplan port, and deletion gates; use native branch as quarry.
- `elegant_split_end_state.md`: clean-break is the final target; no permanent shims, old public graph APIs, or product-local runners.
- `python_dsl_downsides.md` and `python_dsl_roadmap.md`: restricted Python can be optional sugar only after the manifest contract and explicit-node DSL are stable.
- `elegant_split_gap_report.md`, `load_bearing_questions_codex.md`, and combined reviewer answers: native-first authoring is not the final public workflow DSL; kernel primitives must stay mechanism-level; execution must avoid becoming a public graph runner; a serious non-Megaplan proof is needed before Megaplan migration is treated as neutral.
