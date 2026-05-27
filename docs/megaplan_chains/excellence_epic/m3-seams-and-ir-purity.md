# Sprint 3 — Seams + IR purity (`premium/thorough/high +prep`)

Shared context: read `docs/structural_audit_2026-05.md` (lens 1 + Part 2 seam/layering findings j1/j7). Sprint 3 of 10. The differential harness (sprint 1) and consistency gates (sprints 2a/2b) are the regression net. **Breaking public-API changes are authorized for this sprint, shipped behind a minor version bump with a migration note** (user-confirmed).

## Outcome
The IR core stops silently losing user intent and stops leaking ComfyUI internals; the runtime seams converge so the same workflow behaves identically across paths; and the Layer-1 core depends on nothing above it.

## Scope (IN)
0. **Verify the release/version foundation before breaking APIs**: confirm `pyproject.toml`, package version exposure (`__version__` or `importlib.metadata` convention), console entrypoint metadata, and migration/release-note locations exist and are internally consistent. If any are missing or stale, fix them before the public API change.
1. **`set_input` loud** (`workflow.py:244`): currently unmatched input names are parked silently in `metadata["unbound_inputs"]` and never read by `compile()`, so `wf.set_prompt("x"); run(wf)` via the Python API silently ignores the prompt for templates with no registered inputs (e.g. `z_image`). Make it raise `ValueError` on unbound names. Public-API breaking → bump from current `2.7.0` to `2.8.0` unless prep finds a stronger repo convention, plus a versioned release note under `docs/release_notes/v2.8.0.md` and migration examples.
2. **`compile()` edge-rewiring** (`workflow.py:486`): when an edge's source node is UI/helper-stripped, trace through and rewire the edge to the real upstream source instead of silently dropping it. Make `validate()` skip the same stripped nodes so validation and compile agree (today validate passes while compile breaks connectivity).
3. **Unify `run()` vs `run_embedded()` schema validation at the existing boundary**: remove the `cache_only=True` divergence (`session.py:295`) so embedded and server validate consistently; normalize the current queue return shape (HTTP dict vs comfy object) only as much as needed for consistent `metadata.json`. Session creation, runtime registry, `RunResult` expansion, and final runtime dispatch remain sprint-6a-owned.
4. **IR bug fixes**: inputs/widgets merge order (`workflow.py:755`), `finalize_metadata` idempotency/non-destructiveness (`workflow.py:159` clears manually-registered inputs), `connect()` bare-node-id handling (`workflow.py:322` crashes on a dot-less id), `_next_node_id` collision after deletion (`workflow.py:637`).
5. **Move `validate()`'s ComfyUI-specific checks** out of `VibeWorkflow` into `contracts/` so the IR class stays pure.
6. **Define the IR contract before moving code**: add a small code-facing contract module (`vibecomfy/contracts/ir.py`) plus a short prose anchor in `docs/release_notes/v2.8.0.md` describing what `VibeWorkflow.validate()`, `compile("api")`, public inputs, stripped helper nodes, and edge rewiring guarantee. This keeps the sprint from merely relocating coupling. The contract must state at minimum: `set_input(name)` raises on unregistered public inputs; `validate().is_valid` implies `compile("api")` succeeds; every compiled edge endpoint resolves to a compiled node; helper/UI-stripped edges are either rewired or reported, never silently dropped.
7. **Fix the layering violation**: `workflow.py:9-10` imports `vibecomfy.porting`. Extract the exact helpers currently imported from `vibecomfy.porting` by Layer-1 code into `vibecomfy/_workflow_helpers.py` (including `helper_stripped_nodes`/`class_types`, `collect_broadcast_sources`, and `apply_positional_widget_aliases` unless prep proves a narrower set), so the core imports nothing upward. Do not create a second durable classification source here: if helper/UI class sets are needed before sprint 4, expose only an IR-neutral temporary shim and mark sprint 4 as owner of the durable `UI_ONLY_CLASS_TYPES` / `classify_node()` home. Temporary exports that M4 must eliminate or re-home should carry `# REMOVE-M4` comments, and the import-linter contract should prevent new imports of `_workflow_helpers` outside the minimum IR path. Same for `contracts/surface.py`→`porting`. Add an `import-linter` contract asserting the IR core imports nothing from porting/Layer-2/commands.
8. **Revalidate sprint-2a/2b gates after the IR changes**: run `vibecomfy check --json` and any node-spec/schema handoff checks recorded in `handoff-m2b.md`; update only tests/docs if the new IR contract intentionally changes what the gates should assert.
9. **Create the IR handoff artifact** at `docs/megaplan_chains/excellence_epic/handoff-m3.md`, recording public breaking changes, migration examples, import-linter command, and any contract assumptions M6/M7 must preserve.

## Locked decisions
- Breaking changes OK with version bump + migration note.
- The differential harness + snapshots are the regression net.
- `set_input` goes straight to `raise` (not warn-then-raise) since we're version-bumping.
- The extracted Layer-1 helper home is `vibecomfy/_workflow_helpers.py` unless prep finds a concrete reason a method on `VibeWorkflow` is safer.
- Version/release metadata is a prerequisite, not an end-of-sprint afterthought: the sprint may not change public API until the package version source and migration note target are known.
- Release convention is versioned release notes: use `docs/release_notes/v2.8.0.md` and do not introduce a parallel top-level `CHANGELOG.md` unless the repo has adopted one first.

## Prep deliverables
- Prep deliverable: `docs/megaplan_chains/excellence_epic/prep-m3.md` with the IR contract sketch, breaking-change inventory, version bump target, migration-note outline, release-metadata check, and layering extraction map.
- Version number: target `2.8.0` from the current `pyproject.toml` version `2.7.0` unless prep finds the repo's existing versioning convention requires a different explicit target. The repo treats the current `2.x` line as the active major-version umbrella; controlled breaking changes may land in a minor bump only with explicit migration notes. Prep must reconcile this with the v2.7.0 release note's backward-compatible-minor language.
- Import-linter dependency: use the `import-linter` package, add it to the dev/test dependency surface if absent, and commit the config file used by the sprint.

## Constraints
- Differential harness + snapshots stay green (or each change justified).
- Sprint-2a/2b consistency gates stay green after the IR changes, or the handoff explains any intentional gate adjustment.
- Every public-behavior change documented in the migration note + version bump.
- No new layering violations; the import-linter contract must pass.
- Future sprints must keep the import-linter contract green when adding/moving modules.

## Done criteria
- IR imports nothing from `porting/`/Layer-2 (verified by import-linter). The import-linter config must use a single explicit contract with no per-file or per-module exceptions; forbidden imports are eliminated by extraction to `_workflow_helpers.py` or equivalent, not whitelisted.
- `set_input` raises on unbound names (test); `compile()` rewires stripped-helper edges (test); `run()`/`run_embedded()` validate identically (test).
- IR bug fixes each covered by a regression test.
- Release/version foundation verified or fixed: package version source, console entrypoint metadata, migration-note target, and versioned release-note convention are consistent.
- Minimal canonical journey smoke exists and passes: `load_workflow_any("image/z_image") -> set prompt/seed/steps -> validate -> compile("api")`. The smoke must be a discoverable pytest test, preferably in `tests/test_acceptance.py`; `handoff-m3.md` records the test function name, workflow id, and expected compiled node count so M7 can extend the same path to new verbs.
- If sprint-2a/2b gate revalidation requires more than test/doc updates (for example restructuring coverage data or changing gate logic), the delta is an explicit escalation recorded in `handoff-m3.md`.
- Any widget-alias gaps resolved or newly created by IR changes are annotated in `handoff-m3.md` with a cross-reference to `handoff-m1.md` deferred items.
- Migration note + version bump landed, with before/after examples for public API changes.
- Sprint-1 differential harness and sprint-2a/2b gates pass.
- `handoff-m3.md` captures commands, contract decisions, migration notes, and deferred risks.

## Touchpoints
`vibecomfy/workflow.py`, `handles.py`, `metadata.py`, `contracts/surface.py`, `runtime/run.py`, `runtime/session.py`, new `vibecomfy/_workflow_helpers.py`, `docs/migration_*.md`, version in `pyproject.toml`, import-linter config.

## Anti-scope
Do NOT decompose `session.py` (sprint 5 de-dups it). Do NOT build the `VibeSession` factory (sprint 6a). Do NOT touch the emitter (sprint 1 owns it).
