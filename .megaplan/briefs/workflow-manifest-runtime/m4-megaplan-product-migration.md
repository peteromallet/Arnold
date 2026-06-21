# M4: Megaplan Product Migration

## Outcome

Move load-bearing Megaplan product logic to `arnold_pipelines.megaplan` and rewrite the canonical Megaplan planning flow as explicit-node workflow data compiled and run through the manifest runtime.

The reviewer should be able to compare legacy behavior goldens against the new manifest-backed Megaplan pipeline and see that neutral Arnold core remains free of Megaplan imports.

## Operating Philosophy

M4 is the semantic cutover for the load-bearing product. The goal is not to make Megaplan look new while behaving approximately the same; it is to prove the old planning semantics, state/resume behavior, control policy, and operator expectations survive on the manifest runtime while product policy moves out of neutral Arnold. Temporary bridge code exists only to measure and migrate, never to become the new foundation.

## Scope

IN:

- Introduce `arnold_pipelines/__init__.py`, `py.typed`, and `arnold_pipelines/megaplan/` package structure.
- Configure package metadata and wheel/sdist build rules for the new `arnold_pipelines` namespace package when it is introduced. M4 must prove `arnold_pipelines.megaplan`, `py.typed`, package metadata, and `build_pipeline()` work from an installed wheel, not only editable mode.
- Move or re-author Megaplan product stages, prompts, policies, profiles, schemas, receipts, artifacts, plan repository, control interface, runtime capabilities, reducers, and orchestration code behind the new package.
- Register Megaplan content types with the neutral registry: plan, receipt, capsule, delta, gate signal, review output, execution evidence, and any existing state artifacts that must survive migration.
- Implement `arnold_pipelines.megaplan.pipeline.build_pipeline()` using `workflow.Pipeline(..., steps=[...])`.
- Include canonical nodes for prep, plan, critique/review, gate, revise loop, tiebreaker subpipeline/retry path, human gate as product capability over generic suspension, finalize, execute, and post-review where behavior requires it.
- Preserve current 9-stage planning behavior with golden/parity tests and manifest topology/hash tests.
- Preserve all current gate condition semantics as product policy: every existing gate transition family, distinct override force-proceed path, auto-escalation path, blocked-agent preflight path, recursive tiebreaker loop-back, and feedback-phase route must map to explicit manifest/control constructs with parity evidence.
- Preserve gate auto-downgrade: high-complexity unverifiable critique checks must block `PROCEED` and route to `ITERATE` with explicit downgrade rationale and force-proceed override, matching current `handlers/gate.py` behavior.
- Preserve override/fallback routing, feedback-as-phase, robustness-driven dynamic topology, dynamic prompt builders via importable `module:qualname` callables, subpipeline artifact promotion, auto-supervisor transitions, stall/idle/blocked/orphan recovery, and execute-callback-failure recovery.
- Preserve finalize fallback blast radius: when plan metadata lacks `test_blast_radius`, compute scoped pytest selectors from git diff against the execution baseline, matching current `handlers/finalize.py` behavior.
- Preserve execution-evidence hardening: subprocess calls handle missing `git`/timeouts and task-satisfaction staleness accepts ancestor HEAD relations so harness commits between batches do not trigger infinite re-execution loops.
- Preserve execute-prompt `pending` task status for multi-step work requiring separate tool calls.
- Preserve critique-payload normalization by stripping unknown check-level keys as defense against template/schema drift.
- Preserve review-payload normalization: populate target objects, default `deterministic_check` to `None`, and compute `task_ids` from concerned task IDs.
- Preserve dynamic Megaplan manifest-hash resume behavior: missing current hash for the canonical Megaplan pipeline matches the stored legacy sentinel only through an explicit migration rule.
- Add an optional shadow/dual-run seam that compares legacy and manifest-backed runs and writes drift reports before old execution paths are removed.
- The shadow/dual-run seam must produce characterization traces capturing event sequences, artifact hashes, decisions, capability invocations, suspension points, and control transitions from both legacy and manifest-backed runs for structured semantic diff.
- Produce committed `docs/arnold/legacy-surface-inventory.md` and bridge-caller inventory covering `_pipeline`, `_bridge`, `_forward_m2_m3`, `_compatibility`, `builder.py`, `native_runner.py`, `native_hooks.py`, old `arnold.runtime` surfaces, CLI forwarders, subloop callers, resume paths, and demo entries, with M6 deletion status for every entry.
- The legacy inventory must define exactly what `_pipeline` means in this repository: discrete modules, package roots, conceptual API names, re-exported symbols, generated references, docs references, tests, and command surfaces. Include `arnold/pipeline/__init__.py`, `arnold/pipelines/megaplan/__init__.py`, `_core/__init__.py`, package-local builder/executor/type exports, `agent/__init__.py`, dynamic `arnold.agent` shims, and `arnold/pipelines/megaplan/store/legacy_migration.py`.
- Produce committed Megaplan-specific `docs/arnold/state-authority-migration.md`: map old `.megaplan` state formats to event-journal projections and content-addressed artifact roots. M3 owns generic event-journal authority; M4 owns Megaplan historical-state mapping.
- Define whether `state.json` survives as an event-journal projection, migration-period coexistence artifact, or read-only archive. Status, trace, resume, inspect, and override surfaces that survive must derive from manifest events/artifacts/control transitions, and the golden comparison strategy must be documented before tests are written.
- Historical-state policy must cover `.megaplan/plans/*/state.json`, receipts, phase artifacts, locks, nested `.hermes_state`, nested `.megaplan` run directories, telemetry, system/watchdog logs, schemas, briefs, tickets, root plan drafts, and empty placeholder roots. Each class is `migrate`, `project read-only with sunset`, `archive outside the active working tree`, `delete`, or `quarantine with operator-visible rationale`; no class may be silently ignored. Lock files need an owner/PID/TTL/stale-lock policy or explicit archival/deletion rationale.
- Preserve plan-text newline normalization: decode escaped `\n`/`\r\n` in model-returned JSON plan strings to real newlines before Markdown validation.
- Product migration must reroute all `.megaplan/<kind>` artifact writes through the M1 versioned-artifact convention and `ctx.plan_dir` paths where callers are `StepContext`-based.
- Implement or specify one-shot historical state migration tooling for existing plan state, receipts, capsules, gate signals, and artifacts, with explicit exclusions where migration is not required.
- Produce a Megaplan-specific operator command inventory: current command, new command/projection, temporary behavior before M6, and M5/M6 disposition. M5 broadens this repo-wide.
- Route model/tool dispatch through neutral `arnold.agent` and runtime effects/capabilities.
- Preserve `infrastructure_error` characterization: auto-drive corpus and golden recipe behavior for non-retryable infrastructure errors must survive migration or be explicitly reclassified with parity evidence.
- Reconnect Megaplan product identity to the M1 identity derivation table; package discovery, trust classification, tenant derivation, registry IDs, and generated metadata must agree before and after the package move.
- Map every old Megaplan override catalog action to a neutral `ControlTransition` event or delete it with rationale.
- Keep only short-lived transition imports if absolutely necessary, with conformance TODOs that M6 will fail until removed.

OUT:

- No migration of every shipped example pipeline; M5 handles those.
- No final deletion of every legacy surface; M6 handles purge after parity.
- No public restricted-Python authoring.
- No permanent `arnold.pipelines.megaplan`, top-level `megaplan`, `_pipeline`, bridge, native hooks, or native runner compatibility.

## Locked Decisions

- Product runtime code may depend on `arnold.workflow`, `arnold.patterns`, `arnold.execution`, `arnold.agent`, and `arnold.kernel`.
- Neutral Arnold packages must not depend on Megaplan product code.
- Megaplan helpers may set defaults but must not hide topology, side effects, budgets, or dynamic routes.
- Behavior preservation is proven through goldens and parity, not by keeping permanent shims.
- The dirty root-level relocation from `native-python-pipelines` is not a migration strategy.
- `arnold_pipelines.megaplan` is the permanent product home. `arnold.pipelines.megaplan` is an obsolete legacy surface and remains an M6 deletion target.
- Megaplan control policy owns override meanings, fallback meanings, supervisor transitions, reducers, prompt-builder patterns, and product command behavior. Neutral runtime records and dispatches generic control/effect events only.

## Resolved Execution Decisions

- Temporary aliases are allowed only for M4 shadow/parity and must be listed in the legacy-surface inventory with owner, expiry, and M6 deletion row. New Megaplan code changes immediately to `arnold_pipelines.megaplan`.
- CLI/status/trace/inspect/resume/override expectations map to manifest events, artifacts, control transitions, and projections; `state.json` may only participate as migration input or read-only projection with sunset.
- Product-owned behavior includes prompts, policies, reducers, gate meanings, override/fallback meanings, supervisor transitions, robustness choices, tiebreaker policy, and command behavior. Neutral M3 owns execution ordering, event envelopes, idempotency, capability/effect dispatch, suspension, resume, and fail-closed semantics.
- The live-backed smoke matrix after fake-backend parity includes fresh plan, resume from suspension, at least three gate iterations, and tiebreaker execution.
- Old execution paths retained for M4 shadow comparison are listed in the bridge-caller inventory and become M6 deletion rows unless explicitly re-chartered with non-legacy rationale.
- Historical `.megaplan` data is classified by the M4 state ledger as migrate, project read-only with sunset, archive outside active tree, delete, or quarantine with operator-visible rationale.
- Compatibility shim tests and legacy migration helpers survive only as M4 parity/migration evidence. Their post-M4 disposition is migrate/delete/archive with an explicit M6 row; they cannot become permanent keepalive tests.

## Constraints

- Do not move package layout and change behavior in the same untested step.
- Import-boundary and coupling gates must stay green after each package move.
- Keep old and new behavior comparable with normalized fixtures.
- Installed-wheel behavior must be considered even if final wheel gate is M6.
- Do not widen neutral runtime dataclasses just to accommodate Megaplan-specific state.
- Status, trace, and resume should project from manifest events/artifacts rather than product-owned parallel state.
- All operator overrides should flow through one control transition path. Legacy state merge modes must be retired or proven to be read-only projections of control transition events.
- `_core/state.py` authority must shrink toward event projection; it must not remain an independent mutable source of truth after migration.

## Done Criteria

1. `arnold_pipelines.megaplan.pipeline.build_pipeline()` returns the canonical explicit-node Megaplan workflow.
2. The pipeline compiles to a stable manifest and fake-runs through the M3 runner.
3. Golden/parity tests cover planning, revise/gate iteration, override/fallback routes, tiebreaker, human/suspend when available, finalize, execute, review, auto-supervisor transitions, callback recovery, dynamic topology, prompt-as-code, subpipeline promotion, resume-sensitive behavior, plan-text newline normalization, execute-prompt `pending` status, gate auto-downgrade for high-complexity unverifiable checks, finalize fallback blast radius, critique/review payload normalization, execution-evidence subprocess hardening, task-satisfaction ancestor-head staleness, and `infrastructure_error` characterization; semantic manifest diffs pass against locked M2 expected shapes.
4. Gate parity covers every current gate transition family, including blocked-agent/preflight conditions and the two distinct force-proceed paths, and proves recursive tiebreaker can loop at least twice before proceeding.
5. Product code is moved/re-authored under `arnold_pipelines.megaplan` without neutral Arnold importing it.
6. CLI/status/trace/control surfaces needed for Megaplan project manifest-backed events/artifacts or have explicit transition tests.
7. Live-backed smoke covers fresh plan, resume from suspension, at least three gate iterations, and tiebreaker execution against a real backend.
8. Installed-wheel smoke proves `arnold_pipelines.megaplan`, `py.typed`, package metadata, `build_pipeline()`, compile, fake-run, and CLI projection behavior work from a built wheel.
9. Legacy surface, bridge-caller, historical state, and Megaplan operator-command inventories are committed with no undecided entries.
10. Historical state migration proves projection parity for surviving golden runs, including old `state.json` fields, event logs, resume cursors, nested runs, locks, and artifact references; archived/quarantined runs are named with rationale.
11. A nested-state ledger matches `find .megaplan` output for `state.json`, locks, nested `.megaplan` directories, and `.hermes_state`; no undiscovered old state authority remains.
12. Every surviving suspended run has its old resume cursor translated to manifest coordinates or quarantined with operator notification.
13. Product code registers Megaplan content types and artifact adapters without adding product schema knowledge to the neutral kernel.
14. Megaplan registers concrete condition/policy/transition meanings for override, fallback, escalation, compensation, supervisor promotion, robustness variants, feedback phase, and dynamic topology overlays without widening neutral types.
15. If content-type registration, state migration, or legacy inventory discoveries require manifest/kernel contract changes, M4 updates M1/M2/M3 contract tests and `workflow-manifest-amendments.md`.
16. Remaining legacy surfaces are inventoried for M6 deletion with blockers named.

## Touchpoints

- `arnold_pipelines/megaplan/`
- `arnold_pipelines/megaplan/pipeline.py`
- `arnold_pipelines/megaplan/policies/`
- `arnold_pipelines/megaplan/runtime/`
- `arnold_pipelines/megaplan/orchestration/`
- `arnold_pipelines/megaplan/prompts/`
- `arnold_pipelines/megaplan/profiles/`
- `arnold_pipelines/megaplan/schemas/`
- `arnold_pipelines/megaplan/receipts/`
- `docs/arnold/legacy-surface-inventory.md`
- `docs/arnold/state-authority-migration.md`
- historical state migration tooling
- historical state/archive/exclusion ledger for `.megaplan` working data and logs
- package metadata and wheel/sdist configuration for `arnold_pipelines`
- Megaplan operator command mapping
- `tests/arnold_pipelines/megaplan/`
- `tests/fixtures/workflow/`
- Megaplan CLI/status/trace tests

## Anti-Scope

- Do not polish `_pipeline`, bridge, or native runner code as final architecture.
- Do not keep compatibility imports without an M6 deletion gate.
- Do not migrate unrelated example pipelines in this sprint.
- Do not change clean-break policy to satisfy stale consumers without an explicit decision.

## Suggested Run

`partnered-5/thorough/high`

This is the load-bearing product cutover with package moves, import graph changes, public API risk, and behavior preservation risk.
