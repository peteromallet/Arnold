
## Handoff artifacts

- Frozen inventory matrix covering the explicit convert vs out-of-scope decisions for `creative`, `doc`, `jokes`, `live_supervisor`, `deliberation`, the `planning` alias, and `evidence_pack`.
- Parity/resume evidence locations for every converted M6 pipeline.
- Remaining blocker list for M7: rollback gaps, graph-born resume concerns, docs/skills still needing updates.
- Conversion runbook/template reference that future authors can follow.

## No-go conditions

- M5A/M5B have not proven `parallel(...)` and human-gate behavior on real pipelines.
- Kickoff inventory has not been frozen to the explicit target list in this brief.
- Newly discovered pipelines are being silently added to scope after kickoff.
- The `planning` alias or `evidence_pack` status is still ambiguous at milestone start.
# Milestone 6 — Remaining pipeline migrations

## Outcome

All remaining frozen-target graph-backed pipelines run natively behind the feature flag with per-pipeline parity tests, and the epic enters the default-flip milestone with the non-target inventory already decided in writing.

## Scope (IN)

- Convert only the frozen target list below; this is the full M6 migration inventory unless a later milestone explicitly re-scopes it:
  - `creative` — **convert** in M6.
  - `doc` — **convert** in M6.
  - `jokes` — **convert** in M6.
  - `live_supervisor` — **convert** in M6.
  - `deliberation` — **convert** in M6 if M5B did not already complete it; if M5B did complete it, record it as already satisfied and do not reopen it.
- Convert each to a native `@pipeline` function:
  - Preserve handlers and contracts.
  - Use `@phase` / `@decision` decorators with explicit ports.
  - Use `run_subpipeline(...)` and `parallel(...)` where the original graph uses subloops or parallel stages.
  - Use human-gate primitives where needed.
- For each pipeline:
  - Capture a graph-executor golden trace.
  - Assert native parity for stage sequence, `state.json`, `events.ndjson` fold, `resume_cursor.json`, artifacts, and topology hash.
  - Prove native checkpoint resume.
- Update derived `build_pipeline()` exports so `arnold pipelines check` sees native-derived graphs.
- Consolidate common conversion patterns into a short runbook or template so future pipelines can be authored natively from scratch.
- Record the non-target decisions as locked inventory outcomes rather than runtime discoveries:
  - `planning` alias — **out of scope**; it is a thin re-export of canonical `megaplan`, not a separate migration target.
  - `evidence_pack` — **out of scope** for this migration; it is a model-less `in_process` verification pipeline with its own resume surface, not part of the native Python pipeline flip.

## Scope (OUT)

- Any pipeline not listed in the frozen target list above, unless later explicitly re-scoped.
- Flipping the default execution mode to native.
- Removing the graph executor or graph builders.
- Large new runtime features not already provided by Milestones 3–5.

## Locked decisions

- Frozen inventory decision matrix:
  - `creative` — convert.
  - `doc` — convert.
  - `jokes` — convert.
  - `live_supervisor` — convert.
  - `deliberation` — convert unless already completed in M5B, in which case M6 only verifies the handoff and does not reopen scope.
  - `planning` alias — out of scope.
  - `evidence_pack` — out of scope.
- Every converted pipeline must pass parity tests before the milestone is considered done.
- Pipelines are converted one by one; no bulk migration without per-pipeline acceptance.
- The graph executor remains the default for production runs during this milestone.

## Open questions

- What conversion order minimizes risk across `creative`, `doc`, `jokes`, `live_supervisor`, and `deliberation`?
- Are there any target pipelines that rely on graph-executor-specific helpers with no native equivalent yet?
- Which pipelines can share a common native skeleton or helper module?
- Does `doc` need any extra dynamic-fanout documentation or helper extraction once its migration lands?

## Constraints

- Must not break existing tests or in-flight plans.
- Must run behind the existing feature flag.
- Must produce byte-compatible persistence shapes per converted pipeline.
- Must not change the default execution mode.
- Must not let the target inventory silently expand mid-milestone.

## Done criteria

- Every convert-marked target pipeline has a native implementation, except `deliberation` if it was already fully completed in M5B and accepted as satisfied there.
- Each converted pipeline has passing parity tests and a resume test.
- Derived graphs for all converted pipelines pass validation.
- All existing tests still pass.
- The handoff explicitly preserves `planning` alias and `evidence_pack` as out-of-scope inventory decisions.
- A conversion runbook or template is committed.
- Milestone 7 handoff confirms no remaining blockers for flipping the default and lists in-flight compatibility criteria.

## Touchpoints

- `arnold/pipelines/megaplan/pipelines/creative/`
- `arnold/pipelines/megaplan/pipelines/doc/`
- `arnold/pipelines/megaplan/pipelines/jokes/`
- `arnold/pipelines/megaplan/pipelines/live_supervisor/`
- `arnold/pipelines/deliberation/`
- `arnold/pipelines/megaplan/pipelines/planning/` (read-only alias reference)
- `arnold/pipelines/evidence_pack/` (read-only out-of-scope reference)
- `tests/arnold/pipeline/native/parity_corpus/` (extend with new golden traces)
- `docs/arnold/pipelines/native-conversion-runbook.md` (new)

## Anti-scope

- Do not flip the default execution mode.
- Do not remove the graph executor.
- Do not start new feature work unrelated to migration.
- Do not silently add newly discovered pipelines to M6 without an explicit re-scope decision.
