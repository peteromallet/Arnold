# Workflow Manifest Runtime Review Synthesis

Date: 2026-06-21

This plan was optimized through the review process requested in `/Users/peteromalley/Documents/megaplan/plan.md`.

## Wave 1: End-State Review

DeepSeek reviewed ten end-state expectations against `chain.yaml` and the six milestone briefs. Results are stored under:

- `docs/arnold/workflow-manifest-runtime-review/initial-analysis.md`
- `docs/arnold/workflow-manifest-runtime-review/subagent-briefs/w1-*.md`
- `docs/arnold/workflow-manifest-runtime-review/subagent-results/wave1/`

Accepted corrections:

- Shared kernel vocabulary belongs in neutral Arnold packages. Product packages populate policy/capability registries, but the wire contracts, event families, and effect base contracts live under `arnold.kernel`.
- Authoring helpers survive only as compile-time data constructors. No authoring object crosses the compile boundary into execution.
- `arnold.execution` must not import `arnold.patterns`; runtime executes manifests and schema/kernel types only.
- M1 should include a manifest amendment protocol so M2/M3 discoveries do not silently mutate the contract.
- M1 must include artifact binding schema anchors.
- Concrete retry, loop, fanout, and reducer semantics can be finalized in M3, but M1 must reserve deterministic manifest slots for them.
- Generic suspension is runtime-owned and orthogonal to human gates. Megaplan human gates are a product consumer of generic suspension.
- M4 parity must include override/fallback routing, robustness-driven dynamic topology, auto-supervisor transitions, callback recovery, prompt-as-code, and subpipeline promotion.
- M5 must produce a closed pipeline migration/deletion/whitelist inventory before M6 deletion.
- Generated skills, generated projection docs, package authoring docs, templates, package metadata, package disposition, and CLI entrypoint dispatch are public surfaces and must be covered.
- M6 deletion must be traced to M5 outcomes and proven by installed-wheel, import graph, docs/scaffold, metadata, type-surface, and behavior gates.
- A thin M3-to-M4 integration gate must fake-run the canonical Megaplan-shaped manifest before product migration begins.

Rejected corrections:

- Do not keep old import paths alive only to raise migration errors. The clean-break target remains no permanent public `megaplan` or `arnold.pipelines.megaplan` compatibility modules.
- Do not reinterpret `arnold.pipelines.megaplan` as the permanent product home. The permanent product home remains `arnold_pipelines.megaplan`; `arnold.pipelines.megaplan` is an obsolete surface to delete.

## Current Plan Shape

The chain remains six primary milestones:

1. M1: baseline guardrails and manifest/kernel contract.
2. M2: explicit-node DSL and compiler.
3. M3: manifest runner and runtime.
4. M4: Megaplan product migration to `arnold_pipelines.megaplan`.
5. M5: shipped pipelines, CLI, docs, generated surfaces, scaffolds, and inventory.
6. M6: clean-break purge and conformance.

M5 may be executed internally as M5a/M5b workstreams, but the chain artifact remains one milestone unless the operator deliberately splits it.

## Wave 2: Surface-Edge Review

DeepSeek reviewed ten scope edges against the Wave-1-updated briefs. Results are stored under:

- `docs/arnold/workflow-manifest-runtime-review/subagent-briefs/w2-*.md`
- `docs/arnold/workflow-manifest-runtime-review/subagent-results/wave2/`

Accepted corrections:

- Treat `arnold.agent`, `arnold.control`, `arnold.conformance`, and old `arnold.runtime` as explicit surfaces instead of letting them be discovered during implementation.
- Define a neutral capability/effect dispatch seam so `arnold.execution` can invoke agent/tool capabilities through contracts without importing Megaplan product code.
- Add a committed legacy surface inventory and bridge-caller inventory before deletion.
- Expand CLI scope to status, trace, inspect, override, parser snapshots, command mapping, entrypoints, and installed-wheel CLI smoke.
- Add authoring error ergonomics, public/provisional/internal symbol markers, and stable-vs-diagnostic inspect/dry-run field documentation.
- Add cancellation, timeout/deadline, escalation routing, reducer dispatch boundaries, and compensation hooks as runtime semantics.
- Replace kernel `human` ownership with generic `suspension`; human gates are product capability/policy over suspension.
- Add neutral content-type registry, retention contract, provenance chain verification, state-authority migration, and historical state migration.
- Add control/governor/effect-ledger kernel contracts and make the event journal the single source of truth for state, cost, trace, and resume.
- Define old discovery manifest vs. new `WorkflowManifest` coexistence, explicit-node package authoring, pipeline ID registry artifacts, namespace-package wheel configuration, py.typed audit, package disposition validation, and discovery trust migration.
- Add installed-wheel test scaffolding, merge-result conformance, deletion-list subset validation, committed workflow decision docs, and concrete M3-to-M4 fake-run criteria.

Rejected corrections:

- Do not keep a permanent old CLI or import entrypoint purely to emit migration errors. Temporary transition behavior is allowed before M6 only if M6 deletes it.
- Do not remove the broader `arnold.patterns` vocabulary just because Megaplan is the first major consumer. Higher-level patterns may remain public if they are pure manifest-compiling constructors with stability markers and no product policy baked in.
- Do not require old `.megaplan` working data in the repository to be rewritten during plan authoring. The implementation milestone must define migration tooling and gates; this planning pass only specifies them.

## Wave 3: Sequencing And Straggler Review

Codex reviewed sequencing, technical abstractions, and final straggler risk against the Wave-2-updated briefs. Results are stored under:

- `docs/arnold/workflow-manifest-runtime-review/subagent-briefs/w3-*.md`
- `docs/arnold/workflow-manifest-runtime-review/subagent-results/wave3/`

Accepted corrections:

- M2 must produce a named canonical Megaplan-shaped manifest fixture with explicit routing families, and M3 must use that exact fixture for fake-run/replay/resume gates.
- `arnold_pipelines.megaplan` packaging, namespace-package configuration, `py.typed`, and installed-wheel import smoke belong in M4 when the product package is introduced, not deferred to M5.
- M4 must own Megaplan-specific historical state migration and Megaplan-specific operator command mapping; M5 broadens those inventories repo-wide.
- M5 must clarify final package locations for migrated shipped pipelines and generated assets, and treat old `arnold/pipelines/...` paths as source-to-migrate/delete unless explicitly re-chartered.
- M5 must add script/operator-tool, generated-artifact, package-build, and legacy-test inventories so non-code artifacts do not become keepalive roots.
- M6 must block on unresolved drift reports, unresolved CLI/inventory rows, conformance allowlist burn-down, built wheel/sdist checks, generated-artifact freshness, and merge-result conformance.
- M6 should include branch/worktree retirement notes as a classification deliverable, but not delete branches/worktrees automatically.

Rejected corrections:

- Do not make M4 a full broad CLI migration milestone; it only needs the Megaplan-specific command map and transition tests. M5 owns repo-wide CLI/operator migration.
- Do not keep old import or console surfaces alive solely for nice migration errors after M6.

## Wave 4: Exhaustive Surface Inventory Review

DeepSeek reviewed shipped pipeline roots, CLI entrypoints, generated artifacts, tests/fixtures, scripts/tools, packaging metadata, conformance allowlists, runtime state shapes, discovery manifests, and legacy bridge/runtime surfaces. Results are stored under:

- `docs/arnold/workflow-manifest-runtime-review/subagent-briefs/w4-*.md`
- `docs/arnold/workflow-manifest-runtime-review/subagent-results/wave4/`

Accepted corrections:

- M5 must name concrete shipped pipeline roots and dispositions, including Megaplan package pipelines, standalone `evidence_pack`, `folder_audit`, `deliberation`, `_template`, internal examples such as `_deliberation_example`, `briefs`, and known stub packages such as `t19`/`t20`.
- M5 must include generated skills/composed rules, projection docs, package disposition data, pipeline ID registries, docs generators, templates, and final generated-asset locations under the new package layout.
- M5 must inventory scripts/tools/root generators and operator-maintenance utilities, including docs generation, watchdog/backfill/adopt helpers, pipeline registry checks, skill sync, oracle tooling, corpus/golden generators, and duplicate tool copies.
- M5 must inventory broad test roots, not only the obvious old pipeline tests: `tests/arnold/pipeline`, `tests/arnold/pipeline/native`, `tests/arnold/runtime`, `tests/arnold/pipelines/megaplan`, `tests/pipelines`, characterization fixtures, oracle/parity fixtures, root-level `test_*.py`, and legacy shim tests.
- M4/M6 must explicitly handle re-export chokepoints and compatibility shims: `arnold/pipeline/__init__.py`, `arnold/pipelines/megaplan/__init__.py`, `_core/__init__.py`, `_bridge.py`, `_compatibility.py`, `_forward_m2_m3.py`, `native_runner.py`, `native_hooks.py`, `agent/__init__.py`, and dynamic `arnold.agent` shims.
- M1/M2/M3 must clarify the relationship between package discovery manifests, discovery trust classifications, `judge_manifest.py`, `schema_registry.py`, `derive_tenant_id`, pipeline ID registries, and `WorkflowManifest` identity.
- M4 must define historical `.megaplan` migration/archival policy precisely, including stale lock files, nested `.megaplan` conventions, plan state, receipts, artifacts, telemetry/log/archive policy, and explicit exclusions.
- Packaging must be audited when `arnold_pipelines` is introduced: root `pyproject.toml`, console scripts, namespace package inclusion, `py.typed` markers, old package data, and installed-wheel behavior.
- M6 deletion gates must cover dynamic imports and allowlist burn-down, not only static AST imports.

Rejected or downgraded corrections:

- Do not treat the review artifact directory as absent; this review pass is already committed in `docs/arnold/workflow-manifest-runtime-review/`.
- Do not claim `scripts/generate_arnold_docs.py` is missing; it exists and is a high-risk migration surface.
- Do not pull the separate Hermes subproject into this migration unless packaging or public Arnold entrypoints actually include it.
- Do not require every historical `.megaplan` runtime file to be rewritten in-place; the milestone must define migration, projection, archival, and exclusion policy, then gate the chosen behavior.

## Wave 7: Semantic Parity And Version Alignment Review

DeepSeek reviewed whether the milestone sequence proves semantic equivalence, not just file movement or schema shape. Results are stored under:

- `docs/arnold/workflow-manifest-runtime-review/subagent-briefs/w7-*.md`
- `docs/arnold/workflow-manifest-runtime-review/subagent-results/wave7/`

Accepted corrections:

- M2/M3/M4 must prove Megaplan gate semantics explicitly: all current gate transition families, distinct override/auto-escalation paths, recursive tiebreaker loop-back, feedback-phase topology, robustness variants, and execute-authority resume failure.
- Robustness and other planned topology variants are compiled manifest variants. Runtime dynamic overlays are recorded as control-transition events and projected into topology views; they do not mutate the canonical manifest during replay.
- M3 must define manifest-version/run-lineage behavior: every event stores the manifest hash and original manifest reference; in-flight old runs either replay with their original manifest, pass explicit alias/compatibility gates, or are quarantined with operator notification.
- Status, trace, resume, inspect, and override commands that survive must derive from manifest events/artifacts/control transitions, not mutable `state.json` authority or legacy event files.
- Runtime must not dynamically import product callables from manifest strings. Product code registers handlers at startup through protocol-typed capability/effect/control registries; manifests carry refs and schema keys.
- External effect idempotency needs a real key schema/derivation protocol and pre-execution budget reservation/settlement events, not post-hoc booleans.
- Identity must have one derivation chain: `workflow.Pipeline.id` is the stable alias, compiler output produces `manifest_hash`, and registries/discovery/trust/tenant/generated metadata derive from those values.
- `build_pipeline()` should return `workflow.Pipeline`; `WorkflowManifest` is compiler output, not package-authored source.
- Generated artifacts are teaching surfaces. They need provenance, migrated generators before regeneration, semantic compile/fake-run checks for embedded examples, and freshness checks tied to generator source hashes and manifest contract versions.
- M5 whitelist escape hatches must be narrow: no public shipped pipeline with docs/CLI/generated-skill/import surface can be whitelisted as old-native semantics.
- Testing must include locked golden normalization, a canonical fixture matrix rather than a single happy path, semantic manifest diffs, characterization traces, installed-wheel fake/live runs, and final contract/runtime tests against the merge result.
- Later milestones must back-propagate contract discoveries into M1/M2/M3 tests and amendment docs before downstream work proceeds.

Rejected or downgraded corrections:

- Do not make every historical CLI command mandatory forever. The correct rule is that every current command receives an explicit migrate/delete/transition disposition, and every surviving command has event-backed semantic parity.
- Do not treat a single stale lock or archived historical run as requiring automatic lossless migration. The plan must forbid silent skipping, require reporting and operator-visible quarantine, and prove losslessness for runs classified as surviving.
- Do not remove all re-chartering language globally; neutral surfaces can be re-chartered only with non-legacy rationale, owner, expiry, and independent review. Legacy compatibility rows still burn down before M6 completes.

## Wave 9: Deletion Attack Review

DeepSeek attacked the final purge from ten angles: imports, CLI entrypoints, generated artifacts, tests/fixtures, state data, packaging, shipped-pipeline whitelists, discovery identity, capability runtime dispatch, and final merge result. Results are stored under:

- `docs/arnold/workflow-manifest-runtime-review/subagent-briefs/w9-*.md`
- `docs/arnold/workflow-manifest-runtime-review/subagent-results/wave9/`

Accepted corrections:

- M6 must test deletion from a clean built wheel and sdist, not just editable source. It must clean build artifacts, unpack wheel/sdist, inspect `RECORD`, scan type stubs and package data, and run import-failure tests in a fresh environment.
- M6 must audit `__pycache__`/bytecode, `__main__.py`, `python -m` entrypoints, console metadata, parser/help text, shell-completion/help artifacts, and dynamic CLI dispatch chains.
- M6 must instrument runtime imports during the full installed-wheel conformance suite so `importlib`, `__import__`, lazy `__getattr__`, `__all__`, entrypoint loading, and handler registration cannot resolve deleted paths unnoticed.
- M5/M6 must scan generator source, templates, JSON/YAML/TOML/CSV registry data, code fences, composed rules, every `SKILL.md`, and generated package data, not only Python imports.
- M6 must audit xfail/skip markers, test helpers, conftest files, root `test_*.py`, oracle/characterization harnesses, and fixture loaders so tests do not hide deletion casualties or keep old runtime semantics alive.
- Old `.megaplan` state deletion requires filesystem-read instrumentation, nested-state ledgers, lock cleanup, resume-cursor translation/quarantine reports, and generated-artifact scans for old state authority terms.
- Discovery/identity deletion requires a final ledger that recompiles every surviving `build_pipeline()` from the final tree, compares its `manifest_hash` to every registry/discovery/trust/tenant/generated-artifact/resume-cursor reference, and fails stale or orphaned hashes.
- Final merge result needs its own conformance stage after all milestone branches are integrated: rebuild wheel, regenerate artifacts, rerun contract/runtime/conformance tests, verify deleted files were not resurrected by merge resolution, and prove manifest hash coherence.

Rejected or downgraded corrections:

- Do not require `arnold.pipelines.megaplan` import failure in M4 if a short-lived transition/shadow path is still needed. The M4 gate is correct new-package wheel behavior plus explicit transition inventory; M6 is the hard import-failure point.
- Do not ban all historical docs text. Ban copy-pasteable executable old API examples and generated/operator-facing teaching surfaces; archival migration notes can mention old names when clearly non-executable and isolated from agent-facing docs.
- Do not make every `.megaplan` read illegal forever. Migration/projection modules may read old state under an explicit sunset and M6-blocking proof that no surviving operator/runtime path depends on it.

## Load-Bearing Question Review

The ten load-bearing decisions and initial answers are stored in:

- `docs/arnold/workflow-manifest-runtime-review/load-bearing-questions.md`

DeepSeek reviewed one question per agent. Results are stored under:

- `docs/arnold/workflow-manifest-runtime-review/subagent-briefs/lbq-*.md`
- `docs/arnold/workflow-manifest-runtime-review/subagent-results/load-bearing-questions/`

Accepted corrections:

- The neutral/product-boundary answer should name surviving neutral `arnold.agent`/`arnold.control` surfaces and the gated `TYPE_CHECKING` exception.
- The identity answer should define `Pipeline.version` semantics and make CLI semantic fixtures part of the final `id + manifest_hash` derivation evidence.
- The parity answer should name shadow/dual-run characterization traces and carry semantic manifest diffs into M4/M6 gates.
- The control/topology answer should explicitly name compensation and startup protocol registries.
- M5 whitelist rules should require independent review and forbid whitelisted source from containing or teaching old-native patterns.
- M5/M6 need explicit amendment clauses so downstream pipeline/docs/deletion work cannot silently widen M1/M2/M3 contracts.
- Post-merge conformance should rerun full upstream gate suites when any downstream amendment changed earlier contracts.

Rejected or downgraded corrections:

- No milestone-brief edits were needed for runtime source of truth, canonical authoring source, old-state handling, or clean-break proof beyond the wording/precision updates above; the agents found those already reflected.

## Main Refresh Swarm Review

After `origin/main` moved from `9d8b2a4a` to `0035c231` on 2026-06-21, six DeepSeek agents reviewed the refreshed baseline against the six-milestone plan:

- baseline/discovery/identity
- artifact/runtime/resume
- Megaplan product migration/parity
- CLI/docs/generated surfaces
- deletion/conformance
- chain execution mechanics

Results are stored under:

- `docs/arnold/workflow-manifest-runtime-review/subagent-briefs/main-refresh/`
- `docs/arnold/workflow-manifest-runtime-review/subagent-results/main-refresh/`

Accepted corrections:

- M1 now treats `arnold/pipeline/discovery/judge_manifest.py` as the authoritative current-main judge-manifest baseline and requires reconciliation of judge-manifest identity (`piece_version`, `judge_version`, `rubric_hash`) with WorkflowManifest identity (`id + manifest_hash`).
- M1/M3/M4 now bind the mainline StepContext/versioned-artifact work into concrete requirements: dual artifact roots, `vN.<ext>` artifact versions, newest-version reads, and product call-site migration.
- M1/M3/M4 now capture native-first then legacy-fallback resume cursor behavior as a migration/runtime requirement.
- M4 now names the newly landed Megaplan behavior that must survive migration: gate auto-downgrade, finalize fallback blast radius, execution-evidence hardening, plan-text newline normalization, execute `pending` status, critique/review payload normalization, dynamic Megaplan manifest-hash resume, and `infrastructure_error` characterization.
- M5/M6 now explicitly disposition `arnold pipelines describe` through CLI mapping, parser/help snapshots, generated surfaces, installed-wheel smoke, and final retain/migrate/delete proof.
- M6 now expands allowlist globs to concrete file sets, audits `sys.modules` after installed-wheel conformance, scans installed CLI help/completion/dispatch output, blocks legacy skill/docs/discovery/template file reads, and resolves surviving judge-manifest sidecars against final manifest identity or locked regeneration.
- Prep and chain notes now include the refreshed-base operator checklist, `--fresh` rerun guidance, `current_milestone_base_sha` verification, and the fact that DeepSeek provider narrowing has no impact because this chain uses `vendor: codex`.

Rejected or downgraded corrections:

- No new sprint split was needed; the six-sprint chain still holds.
- Worker and engine-isolation fixes through `0035c231` improve harness reliability but do not change the epic decomposition.
