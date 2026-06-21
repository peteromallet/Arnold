# M1: Baseline Guardrails And Manifest Contract

## Outcome

Create a clean `workflow-manifest-runtime` implementation branch from `origin/main`, freeze behavior-preservation guardrails, and define the durable Arnold workflow manifest/kernel contract that later milestones must implement.

The reviewer should be able to see a committed manifest v1 contract, golden/parity fixtures, conformance gates, and a quarry map that says exactly what is preserved or rejected from `native-python-pipelines` and adjacent branches.

## Operating Philosophy

M1 is the foundation, not an implementation shortcut. It freezes the vocabulary, identity, event, artifact, and boundary contracts that every later milestone must respect, while treating old/native branches as quarry rather than architecture. The work should bias toward explicit durable contracts over clever compatibility and should make later drift visible through amendment gates instead of hidden in implementation.

## Scope

IN:

- Start from `origin/main`; do not merge or base on `native-python-pipelines`.
- Add or update `docs/arnold/workflow-migration.md` with the branch decision, quarry inventory, rejected native-first surfaces, and milestone handoffs.
- Capture mainline Megaplan behavior with normalized golden fixtures for fresh planning, gate iteration, tiebreaker, human/suspension if available, finalize/execute/review, and resume-sensitive paths.
- Add a no-regression rule that import/package-only moves cannot update behavioral goldens without explicit explanation.
- Define `WorkflowManifest` v1 dataclasses/serialization and core validation for nodes, refs, edges, policies, source spans, capabilities, budgets, retry, loop, fanout, subpipeline, generic suspension/capability routes, reentry IDs, topology hash, and manifest hash.
- Define event/journal/artifact/capability/id/effect/suspension/replay kernel contracts enough for later runner work.
- Define shared kernel vocabulary in neutral Arnold packages: capability identifiers, effect contract base types, event family identifiers, artifact binding schema, and policy-neutral dispatch keys. Product packages may register concrete policy/capability meanings later, but the wire contracts must not live in Megaplan product code.
- Define neutral control, governor, effect-ledger, and content-type registry contracts: `ControlBinding`, `ControlTarget`, `ControlTransition`, control projections, budget/governor carriers, effect idempotency keys, content-type registration, retention pins, and provenance-chain fields.
- Content-type contracts must include `type_id`, `schema_version`, `schema_hash`, retention policy, and provenance parent links.
- Add a dispatch ownership table: `arnold.kernel` defines capability/effect protocols and schema contracts; `arnold.execution` owns registries/invocation/event ordering; `arnold.agent` supplies tool/model adapters; product packages register handlers, policies, prompts, reducers, and control meanings.
- Define how existing discovery/package manifests coexist with or are superseded by `WorkflowManifest` v1. Package discovery manifests are not runtime manifests, but the plan must state whether they survive as package metadata and how trust gates map to workflow manifests.
- Define the old-to-new identity/discovery map explicitly: package discovery manifest fields, `judge_manifest.py` sidecars, discovery trust classes such as auto-executable/quarantined/blessed, `schema_registry.py`, tenant derivation helpers such as `derive_tenant_id`, and pipeline ID registries must each be retained, renamed, superseded, or marked for deletion with rationale.
- Treat `arnold/pipeline/discovery/judge_manifest.py` as the authoritative current-main baseline for judge manifest primitives: `JudgePieceManifest`, `JudgeManifestPort`, `compute_piece_version`, `compute_judge_version`, `make_judge_manifest`, `load_judge_manifest`, and `dump_judge_manifest`. The Megaplan bridge at `arnold/pipelines/megaplan/judge_manifest.py` is a temporary surface burned down by M6 unless explicitly re-chartered.
- Add `docs/arnold/workflow-manifest-amendments.md` with the version-bump and review protocol for any downstream milestone discovery that requires manifest/kernel contract changes.
- Define manifest/run lineage: every journaled event carries the manifest hash and original manifest reference needed for replay. A manifest version bump must state whether in-flight runs replay with the original manifest, use explicit compatibility/alias gates, or quarantine with operator-visible notification.
- Define the control-transition event family. Control events carry transition type, source/target node refs, trigger, payload schema hash, policy ref, and idempotency key. Product packages register meanings for override, fallback, escalation, supervisor promotion, compensation, and dynamic topology overlays; kernel owns the event envelope.
- Define planned topology variants versus runtime overlays: robustness levels and optional feedback phases produce distinct compiled manifest variants; runtime overlays are control-transition events projected into views and do not mutate the canonical manifest.
- Define external-effect idempotency as a key schema plus product-registered derivation protocol; the kernel records the derived idempotency key before execution and uses it for replay de-duplication.
- Define canonical identity derivation: `workflow.Pipeline.id` is the stable human-chosen alias, `WorkflowManifest.manifest_hash` is compiler-computed over the normalized manifest, and pipeline registries, discovery manifests, trust classification, tenant derivation, and generated metadata derive from `id + manifest_hash` rather than carrying independent identities.
- Define `Pipeline.version` semantics explicitly: it is authoring metadata unless promoted by this M1 identity contract; `manifest_hash` is the runtime identity discriminator used by replay, registry, and deletion gates.
- Reconcile judge-manifest identity (`piece_version`, `judge_version`, `rubric_hash`) with WorkflowManifest identity (`id + manifest_hash`). Declare whether judge manifests survive as independent sidecar artifacts with their own hash lineage, are absorbed as `WorkflowManifest` sub-records keyed by `manifest_hash`, or are regenerated from the compiler's manifest hash with explicit provenance. If orthogonal, define the boundary and cross-reference rules.
- Capture the current mainline dual artifact-root model: `.megaplan/<kind>` for repo-root callers and `ctx.plan_dir/<kind>` for `StepContext` callers. The neutral `artifact_dir` contract must represent both without leaking Megaplan product policy into the kernel.
- Freeze the mainline `vN.<ext>` versioned-artifact naming convention: version-number derivation, `latest_version`/`next_version_path` semantics, and the rule that versioned paths are canonical for generated artifacts, golden fixtures, and content-type registry provenance.
- Capture the mainline dual-cursor resume pattern: native-first cursor via `read_native_cursor`, falling back to legacy graph cursor. The M1 contract must define how manifest-coordinate cursors resolve against both shapes during migration.
- Define `GeneratedArtifactProvenance`: generator module, generator source hash, manifest contract version, generation timestamp, and hashed input surfaces for regenerated docs, skills, registries, scaffolds, and package-disposition artifacts.
- Define a locked golden normalization spec: list every volatile field, the canonical normalization transform, ordering rules, seed handling, and the amendment process required to add a new volatile field after M1.
- Commit a repo-local snapshot or summary of the `/tmp/workflow_decision_docs/` source material so M1 is not dependent on ephemeral `/tmp` files.
- Add import-boundary tests proving neutral `arnold.*` packages do not import Megaplan product code.

OUT:

- No public DSL implementation beyond what is needed to test manifest dataclasses.
- No runner execution engine.
- No package move to `arnold_pipelines.megaplan`.
- No deletion of legacy Megaplan paths.
- No restricted-Python generator DSL work.

## Locked Decisions

- The chosen architecture is an explicit-node Python data DSL that compiles to a durable Arnold workflow manifest.
- The runtime executes the manifest, not Python object graphs, generator frames, live callables, `NativeProgram`, or package-private graph executors.
- `origin/main` is the base branch; `native-python-pipelines` is quarry only.
- Clean-break end state is authoritative: no permanent top-level `megaplan`, `arnold.pipelines.megaplan`, `_pipeline`, bridge, compatibility re-export, public `PipelineBuilder`, `Stage`, `Edge`, or `ParallelStage`.
- Restricted Python generator syntax is context only and may later lower to the same manifest; it is not canonical for this migration.
- Authoring helpers, including `arnold.patterns`, are compile-time data constructors only. They produce pure values that compile to a manifest and must not be consumed directly by execution modules.
- Generic suspension is a runtime/kernel primitive, not a human-gate synonym. A node may be suspendable without using the human capability, and a human-capable node need not suspend.
- `arnold.agent`, `arnold.control`, and `arnold.conformance` are neutral surfaces if they survive. They must pass the same neutral-to-product import-boundary rules as `arnold.workflow`, `arnold.kernel`, and `arnold.execution`.
- `arnold.runtime` is legacy runtime surface unless explicitly carved out by M3. M1 must inventory what contract pieces, if any, are preserved under `arnold.kernel` or `arnold.execution`.

## Resolved Execution Decisions

- Fixture coverage is an M1 deliverable: existing Megaplan goldens are inventoried first, then missing route coverage is added for fresh planning, gate iteration, tiebreaker, human/suspension, finalize/execute/review, override/fallback, and resume-sensitive paths.
- Existing event/replay code on `main` is quarry only until classified. Reusable schema, journal, artifact, ID, and replay concepts move under `arnold.kernel` or `arnold.execution`; old public `arnold.runtime` surfaces are M6 deletion targets unless explicitly re-chartered as neutral API.
- Branch fixes from `vibecomfy-codex-contract-fix`, `arnold-pipeline-friction-codex`, and `native-python-pipelines` are harvested only through the quarry inventory, never by merging those branches wholesale.
- M1 freezes the minimal manifest schema needed for M2 authoring plus deterministic reserved slots for M3 runtime semantics. Later discoveries use `workflow-manifest-amendments.md`; they do not silently widen the contract.
- Retry, loop, fanout, reducer, suspension, control-transition, and effect/idempotency carriers are represented in M1 as stable manifest/kernel slots; detailed execution algorithms are finalized in M3.
- `arnold.control` survives only as neutral control API. Package discovery manifests survive only as regenerated package metadata derived from `id + manifest_hash`. Old `arnold.runtime` and old discovery runtime paths are deleted or explicitly re-chartered through M3/M4 inventories.
- Stable public content-type contract fields are `type_id`, `schema_version`, `schema_hash`, retention policy, and provenance parent links. Product-owned schema metadata is registered through product packages without entering neutral kernel types.
- Existing runs are classified during M4 state migration, not left ambiguous: surviving, archived, quarantined, or intentionally abandoned with operator-visible rationale.

## Constraints

- Do not touch unrelated dirty work in the current checkout; create the actual implementation branch from a clean `origin/main`.
- Use the decision docs under `/tmp/workflow_decision_docs/` as source material, but make committed docs self-contained.
- Prefer structured dataclasses/serialization over ad hoc dict/string contracts.
- Hashes, source spans, IDs, and event fields must be deterministic.
- Tests must use `python -m pytest`.
- If `TYPE_CHECKING` imports across the neutral/product boundary are permitted, the exception must be explicit and scanner-enforced. Otherwise all neutral-to-product imports, including type-only imports, fail conformance.

## Done Criteria

1. The migration branch is based on `origin/main`.
2. The quarry/rejection inventory is committed and explicitly rejects native-first public architecture.
3. Baseline golden/parity fixtures exist and are normalized for volatile fields.
4. Manifest v1 and kernel contract modules exist with focused schema/hash/ref/event tests.
5. Import-boundary conformance proves neutral Arnold code does not import Megaplan product code.
6. Artifact binding, content-type registration, retention pins, provenance chains, and generic suspension are represented in the manifest/kernel contract.
7. Control, governor, and effect-ledger contracts are defined without product policy.
8. A manifest amendment protocol exists and is referenced by later milestones.
9. Workflow decision source material is committed or summarized in-repo.
10. Installed-wheel conformance scaffolding exists so later milestones can prove import and entrypoint behavior from a built wheel.
11. Golden normalization, manifest/run lineage, identity derivation, control-transition, idempotency, and generated-artifact provenance contracts are documented and covered by focused tests.
12. The next milestone can build `arnold.workflow` and `arnold.patterns` against a stable manifest contract.
13. A committed table maps every discovery trust classification (`auto-executable`, `quarantined`, `blessed`, and any current-main aliases) to its identity anchor: `piece_version`/`judge_version` for surviving judge manifests, `manifest_hash` for workflow manifests, or both with explicit cross-reference rules. No trust row is identity-ambiguous.

## Touchpoints

- `docs/arnold/workflow-migration.md`
- `arnold/workflow/manifests.py`
- `arnold/workflow/refs.py`
- `arnold/workflow/validation.py`
- `arnold/kernel/ids.py`
- `arnold/kernel/events.py`
- `arnold/kernel/artifacts.py`
- `arnold/kernel/capabilities.py`
- `arnold/kernel/suspension.py`
- `arnold/kernel/content_types.py`
- `arnold/kernel/control.py`
- `arnold/kernel/governor.py`
- `arnold/kernel/effect_ledger.py`
- `arnold/kernel/effect.py`
- `arnold/kernel/journal.py`
- `arnold/kernel/replay.py`
- `docs/arnold/workflow-manifest-amendments.md`
- discovery manifest, trust, schema registry, tenant derivation, and pipeline ID registry disposition notes
- `arnold/pipeline/discovery/judge_manifest.py`
- `arnold/pipeline/discovery/manifest.py`
- `tests/fixtures/workflow/`
- `tests/arnold/workflow/`
- `tests/arnold/kernel/`
- `tests/arnold/conformance/`
- `tests/installed_wheel/` or equivalent wheel smoke scaffolding

## Anti-Scope

- Do not preserve behavior through permanent compatibility shims.
- Do not rename packages in this sprint.
- Do not port `arnold/pipeline/native/*` as product architecture.
- Do not treat package discovery manifests as workflow runtime manifests.
- Do not update behavioral goldens for migration convenience.

## Suggested Run

`partnered-5/thorough/high`

This sprint is architecture-sensitive but primarily contract-freezing and guardrail work; the later public/runtime cutovers carry the highest contract risk.
