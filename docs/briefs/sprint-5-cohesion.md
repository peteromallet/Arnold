# Sprint 5 — Structure & cohesion

Sprints 1–4 built the primitive surface and made it runnable. This
sprint pays down the structural debt that surfaced during the
sense-check: too many parallel pipelines, inconsistent artifact
layouts, plan-mode features that haven't been generalised, no CLI
surface for invoking pipelines, and a mediocre name for the central
abstraction.

## The honest list of cohesion gaps (sense-check findings)

1. **Two pipeline compilations.** `compile_planning_pipeline()`
   (legacy state-name shape, for parity tests) and
   `compile_runnable_pipeline()` (phase-name shape, actually
   runnable). They exist in parallel because the former passes
   the WORKFLOW byte-for-byte inversion test and the latter
   doesn't. **Cost:** confusion about which to use. **Fix:** make
   the runnable shape canonical, retire the legacy one + parity
   test.

2. **Inconsistent artifact layouts.** Doc-critique uses
   `<root>/critique_versions/critique_v<n>.json`; judges uses
   `<root>/judges/<name>/verdict.json`; planning uses
   `<root>/plan_v<n>.md`; subloop uses `<root>/<subloop_name>/`.
   The versioned-artifact helpers (Sprint 4.5) exist but no Step
   uses them. **Fix:** migrate every shipped Step to
   `next_version_path(ctx, kind, ext)` so the layout is
   `<plan_dir>/<kind>/v<n>.<ext>` everywhere.

3. **State.json is shared with a merge workaround.** The handler
   writes plan_versions/history/meta; the executor writes its
   tracked keys; `executor_owned_keys` exists to merge. **Fix:**
   make the contract explicit: handlers own keys X/Y/Z, executor
   owns A/B; one writer per key, no merge needed.

4. **Two Step variants for handler delegation.** `HandlerStep`
   (subprocess) and `InProcessHandlerStep` (in-process) both exist.
   The named classes (PrepStep / PlanStep / …) delegate to the
   in-process variant; subprocess shim is dead code in production.
   **Fix:** decide on one and delete the other.

5. **Plan-mode features that aren't primitives:**
   - **Receipts** (`step_receipt_*.json` per phase) — could be a
     `ReceiptDecorator` wrapping any Step.
   - **Faults registry** (`faults.json` with flag iteration
     history) — could be a typed `FaultRegistry` primitive that
     judge-kind Steps populate.
   - **Resume cursors** (`state.json::resume_cursor`) — could be
     auto-derived from the executor's edge dispatch.
   - **Persistent sessions** (Claude/Codex session IDs by phase
     key) — could be a `SessionBinding` carried on `StepContext`.

6. **No CLI surface.** `megaplan run <pipeline-name>` doesn't exist;
   users invoke via `python -m megaplan._pipeline.demos.doc_critique`
   or write their own driver.

7. **`auto.py` still uses `drive()` (legacy 1700-LOC loop).** The
   new runtime works (test_pipeline_runnable_e2e) but production
   `megaplan auto` doesn't use it.

8. **Naming.** `Pipeline` suggests linear; the value is a directed
   graph with loops + branches + fan-out + escapes. Real
   alternatives:
   - **Workflow** — most accurate, common term, conveys
     branching.
   - **Flow** — short but generic.
   - **Recipe** — cute but unfamiliar.
   - **Graph** — accurate, jargony.
   My recommendation: **Workflow**. Cost: every test, doc, commit
   needs the rename. Upside: clarity for new contributors.

9. **Compose ergonomics.** Building a 4-stage pipeline takes ~30
   lines today. Could be more concise with a fluent builder:
   `Workflow.builder().stage("prep", PrepStep()).then("plan", PlanStep()).fanout(...).build()`.

10. **Profile drive-through.** `PrepStep.slot="prep"` is declared
    but production handlers don't actually consult `ctx.profile.model_for(slot)`.
    Mode dispatch via PromptRegistry has the same gap for real
    handler runs.

## Sprint 5 chunks

Six chunks, mirroring the Sprint 4 structure. Each is
self-contained, testable, and lands a clear cohesion win.

### Chunk A (days 1–2): converge to one pipeline compilation

- Delete `compile_planning_pipeline()` (the legacy state-name
  shape). Make `compile_runnable_pipeline()` the canonical
  `compile_planning_pipeline()`.
- Retire `workflow_dict_from_pipeline()` and the byte-for-byte
  parity tests. The shape is intentionally different now; the
  WORKFLOW dict in `_core/workflow_data.py` stays only as the
  bootstrap data for `_workflow_for_robustness`.
- Update parity tests to assert end-to-end behaviour (a plan
  reaches `done`), not edge-by-edge equivalence with the legacy
  shape.

**Acceptance:** one `compile_planning_pipeline()` function, no
`compile_runnable_pipeline()` lingering. `test_pipeline_runnable_e2e`
passes against the renamed function.

### Chunk B (days 3–4): consistent artifact layout

- Migrate every shipped Step (`PrepStep`, `PlanStep`, `CritiqueStep`,
  `GateStep`, `ReviseStep`, `FinalizeStep`, `ExecuteStep`,
  `ReviewStep`, `DocCritic`, `DocReviser`, the 3 judges,
  `Synthesize`) to write via `next_version_path(ctx, kind, ext)`.
- Layout becomes `<plan_dir>/<kind>/v<n>.<ext>` for every artifact.
- Update the existing tests that hardcoded the old paths to use
  the new layout (or use the helpers themselves).

**Acceptance:** `git grep -E "(critique_versions|doc_versions|judges/judge_)"`
returns hits only in the helpers (or zero). Every Step's output
paths match the convention.

### Chunk C (days 5–6): explicit state.json ownership

- Document which keys the executor owns vs which the handler owns.
- Delete the `executor_owned_keys` workaround in
  `_merge_state_to_disk` — instead have the executor write to a
  separate `pipeline_state.json` and have the handler keep
  `state.json`. State propagation between stages reads from both.
- Or: have the handler-backed Steps return the keys they want
  preserved via `StepResult.state_patch` explicitly, so the
  executor's tracked dict matches reality.

**Acceptance:** no merge workaround in the executor. State.json
ownership is documented + tested.

### Chunk D (days 7–9): plan-mode features as primitives

- **ReceiptDecorator**: wraps any Step; on success/failure writes
  `<plan_dir>/<stage_name>/receipt.json` with timestamps, cost,
  model spec, artifact hashes. Replaces handler-internal
  `_write_step_receipt`.
- **FaultRegistry**: typed primitive that judge-kind Steps
  populate via `ctx.faults.add(Fault(...))`. Persists to
  `<plan_dir>/faults.json` with iteration history. CritiqueStep
  migrates to use it.
- **Resume primitive**: executor exposes a `resume_from(name)`
  function that re-enters a pipeline at the named stage.
  `state.json::resume_cursor` becomes typed `ResumeCursor`.

**Acceptance:** three new primitives shipped. Tests prove each
in isolation + integration with the existing demos.

### Chunk E (days 10–11): CLI surface + rename

- New CLI subcommand: `megaplan run <pipeline-name> [--plan-dir
  <path>] [--inputs key=value,...] [--mode <mode>] [--profile
  <name>]`. Lists registered pipelines via `megaplan run --list`.
- **Rename `Pipeline` → `Workflow`** across the codebase. Update
  every reference (types, tests, docs, registry, briefs). Keep
  a one-release deprecation alias `Pipeline = Workflow`.
- Or, if rename is too disruptive: explicitly decide to keep
  `Pipeline` and document the choice.

**Acceptance:** `megaplan run doc-critique --inputs doc=fixture.md`
drives the demo end-to-end. Naming decision documented in
`docs/pipeline-architecture.md`.

### Chunk F (days 12–14): `auto.py` migration + polish

- Rewrite `auto.py::run_auto` to delegate to
  `run_pipeline_with_policy` when `MEGAPLAN_PIPELINE_AUTO=1`
  (default OFF) or unconditionally (default ON after parity
  CI run).
- Add a fluent builder for ergonomic pipeline construction:
  `Workflow.builder().stage("prep", PrepStep()).then("plan", PlanStep()).build()`.
- Update `docs/pipeline-architecture.md` with the canonical
  story.
- Final test sweep + version tag.

**Acceptance:** `megaplan auto` runs through the new runtime by
default (or env-gated, depending on confidence). Builder API
shipped. Docs reflect the post-Sprint-5 architecture.

## What this sprint deliberately does NOT do

- Full kind taxonomy completeness (subloop already done in
  Chunk D Sprint 4; override edges shipped).
- Cross-pipeline composition (`Workflow.compose(other)`) — defer
  until the use case appears.
- Cloud / Hermes / Resident integration — out of scope.

## Robustness recommendation

`--robustness robust --profile all-claude --depth high` for the
megaplan invocations driving each chunk. Chunks A, B, F are bigger
refactors that benefit from robust; C, D, E are tighter additions
that could use light.

## Definition of done

- One `compile_planning_pipeline()` (legacy retired).
- One artifact layout everywhere (`<plan_dir>/<kind>/v<n>.<ext>`).
- No state-merge workaround in the executor.
- Receipts + Faults + Resume as named primitives.
- `megaplan run <pipeline-name>` CLI works end-to-end.
- Naming decision made + documented (probably `Workflow`).
- `auto.py` walks the new runtime (env-gated or default).
- Full `pytest tests/` stays green (no regressions in the 1837
  existing tests).
- Live `megaplan` binary still resolves to main checkout.

## Risk register

- **Rename churn.** Renaming `Pipeline → Workflow` touches every
  test file. Mitigate via a one-pass script + a deprecation alias.
- **State.json ownership refactor.** Touches the merge logic the
  whole runtime depends on. Mitigate by keeping the workaround
  behind a feature flag until the new contract proves itself.
- **`auto.py` rewrite.** 1700 LOC; high regression surface.
  Mitigate by env-var gate + side-by-side parity test for at
  least one full chunk before flipping the default.
