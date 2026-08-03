# a02-s01-identity-version-provenance-prep-plan: identity-version-provenance × prep-plan

## Verdict

Nonconformant. Static inspection proves several P1 gaps; no P0 is proven without executing concurrent production paths.

The strongest issue is authority mutation: `prep.json` and plan artifacts are written and consumed without a required binding to run, attempt, incarnation, version, and launch provenance. Existing source-binding, active-step, runner-incarnation, and WBC mechanisms are individually useful but are not a single enforced contract.

I searched with `rg --files` and `rg -n` across `arnold_pipelines`, `tests`, `docs`, and wrappers for `run_id`, `attempt`, `incarnation`, `version`, `launch`, `provenance`, `prep.json`, plan parsing, state writes, receipts, phase results, and all direct callers of the relevant symbols.

## Intended canonical contract

Admission should create an immutable decision identity containing:

- plan/run identity;
- phase invocation and ordinal attempt;
- runner incarnation, PID namespace, and process-start identity;
- plan/config/code/template versions;
- provider/model/launch provenance;
- upstream artifact hashes.

Every writer must persist that identity with state and artifacts. Every reader must compare it with current state before using the artifact; mismatch must fail closed.

Existing canonical pieces are:

- source hashing and freshness checks: `arnold_pipelines/megaplan/planning/source_binding.py:60-99,236-260`;
- active invocation/attempt and orphan fence: `arnold_pipelines/megaplan/_core/state.py:1908-1963`;
- runner incarnation and lease binding: `arnold_pipelines/megaplan/_core/phase_runtime.py:63-112`;
- WBC attempt identity/version records: `arnold_pipelines/megaplan/custody/phase_wbc.py:266-307,735-754`.

There is no canonical implementation that composes all of these for prep-to-plan decisions.

## Evidence and complete path inventory

Writers:

- Initial state is created by `handle_init`; admission records only writer, selector, source, and directory-absence fence (`arnold_pipelines/megaplan/handlers/init.py:459-485`), then writes state without run/attempt/incarnation/launch identity (`:489-510`).
- Mock prep writes `prep.json` through `_write_json_artifact` (`arnold_pipelines/megaplan/handlers/plan.py:234-237`).
- Orchestrated prep writes triage, skip, research, metrics, dossier, and final `prep.json` (`arnold_pipelines/megaplan/orchestration/prep_research.py:1099-1149,1159-1170`).
- Plan writes `plan_vN.md` and metadata (`arnold_pipelines/megaplan/handlers/shared.py:1199-1263`); step editing writes another plan version/meta path without identity fields (`arnold_pipelines/megaplan/execute/step_edit.py:100-129`).
- Receipts and phase results are emitted by `_finish_step` (`arnold_pipelines/megaplan/handlers/shared.py:525-555`) and `_emit_phase_result` (`arnold_pipelines/megaplan/orchestration/phase_result.py:710-745`).

Readers/callers:

- `handle_plan` reads prep-derived surfaces and invokes the worker (`arnold_pipelines/megaplan/handlers/plan.py:155-199`).
- The planning prompt reads `prep.json` directly (`arnold_pipelines/megaplan/prompts/planning.py:157-196`; `arnold_pipelines/megaplan/prompts/_shared.py:225-234`).
- Blast-radius derivation treats `prep.json` as authoritative (`arnold_pipelines/megaplan/handlers/plan.py:110-151`).
- Receipts read prep and state snapshots (`arnold_pipelines/megaplan/receipts/extractors.py:337-355`).
- Plan parsing is consumed by step editing (`arnold_pipelines/megaplan/execute/step_edit.py:173-190`) and structural validation (`arnold_pipelines/megaplan/orchestration/plan_structure.py:48-169`).
- Latest-plan consumers resolve only the state’s filename/hash record (`arnold_pipelines/megaplan/_core/state.py:2182-2196`).

The prep schema requires only content fields and has no provenance envelope (`arnold_pipelines/megaplan/schemas/runtime.py:304-378`). The checked-in prep-to-plan fixture likewise records only `current_invocation_id`, not run, attempt, incarnation, version, or launch provenance (`docs/arnold/megaplan-native-representation-boundary-fixtures/prep_to_plan/state.json:1-22`; phase result `:1-12`; boundary receipt `:1-16`).

## Adherence gaps

- **P1 — authority mutation: initial admission does not establish the required identity.** `validate_admission_mutation` validates selector/source/fences only (`arnold_pipelines/megaplan/custody/admission_control.py:157-224`). `handle_init` then creates state with name/iteration/config/history but no run identity, incarnation, launch record, or immutable version binding (`arnold_pipelines/megaplan/handlers/init.py:489-510`). `PlanState` and the storage `Plan` schema also omit those required fields (`arnold_pipelines/megaplan/types.py:211-228`; `arnold_pipelines/megaplan/schemas/sprint1.py:216-245`).

- **P1 — authority mutation: prep subphases bypass per-decision custody.** The outer prep invocation gets an active step and WBC activation (`arnold_pipelines/megaplan/handlers/plan.py:274-278`), but triage/fanout/distill call `run_step_with_worker` without `wbc_dispatch` (`arnold_pipelines/megaplan/orchestration/prep_research.py:419-437`). That function explicitly selects the legacy path when dispatch is absent (`arnold_pipelines/megaplan/workers/_impl.py:6788-6840`). Their outputs are reduced to compatible content keys, discarding any identity fields (`arnold_pipelines/megaplan/orchestration/prep_research.py:44-58,277-278`), before final `prep.json` becomes authoritative (`:1141-1149`).

- **P1 — authority mutation: plan consumes unbound/stale prep evidence.** Both the prompt and blast-radius logic read `prep.json` directly with no current-attempt, hash, phase-result, or source/version check (`arnold_pipelines/megaplan/prompts/_shared.py:225-234`; `arnold_pipelines/megaplan/handlers/plan.py:75-115`). The receipt contract explicitly supplies no upstream hash for plan (`arnold_pipelines/megaplan/receipts/schema.py:129-134`). A corrupt or absent prep file is converted to an empty surface list (`handlers/plan.py:75-92`), producing a potentially false low-scope plan rather than blocking.

- **P1 — authority mutation/status misreporting: plan cleanup is not occurrence-guarded.** `_finish_step` computes `effective_run_id` but clears using the original argument (`arnold_pipelines/megaplan/handlers/shared.py:903-909,1098-1099`). `handle_plan` does not pass its worker’s run ID (`arnold_pipelines/megaplan/handlers/plan.py:208-221`), and `clear_active_step` clears unconditionally when `run_id` is `None` (`arnold_pipelines/megaplan/_core/state.py:1994-2002`). A replacement invocation can therefore have its active authority erased by an older completion.

- **P1 — status misreporting: phase-result emission can silently leave missing or stale evidence.** The documented canonical emitter returns without writing when invocation state is absent (`arnold_pipelines/megaplan/orchestration/phase_result.py:724-745`). Read validation also accepts pre-version artifacts (`:690-702`). `PhaseResult` contains phase and invocation only, not run, attempt, incarnation, version, or launch provenance (`:303-349`).

- **P1 — evidence misbinding: receipts collapse attempts.** `Receipt` has an `attempt` field, but `build_receipt` hardcodes it to `1` and omits run/incarnation/launch identity (`arnold_pipelines/megaplan/receipts/schema.py:12-44`; `arnold_pipelines/megaplan/receipts/__init__.py:110-142`).

- **P1 — authority mutation: recovery can accept unbound provider/file output.** The local-strict path is properly attested and exact (`arnold_pipelines/megaplan/model_seam.py:356-412`), but general recovery reads `<step>_output.json`—including `plan_output.json`—and accepts structurally valid content without identity attestation (`:1578-1658`). Hermes also independently extracts the first JSON object from prose/reasoning (`arnold_pipelines/megaplan/workers/hermes.py:1471-1495,3037-3089`), while worker plan capture has another extractor (`arnold_pipelines/megaplan/workers/_impl.py:4234-4247`). These are reachable bypass/duplicate implementations.

- **P2 — status/evidence gap: structural parsing is identity-blind.** `parse_plan_sections` and `validate_plan_structure` check headings, ordering, substeps, and file references only (`arnold_pipelines/megaplan/orchestration/plan_structure.py:48-169`). They cannot reject a structurally valid artifact from another attempt/version.

## Incident reachability and severity

The reachable path is:

`handle_prep` → nested legacy worker calls → unbound `prep.json` → planning prompt/blast-radius reader → `_run_worker`/provider parser → `_write_plan_version` → `plan_versions`.

The known JSON-decode failure can enter through Hermes’ repair/extraction path, but the independently evidenced issue is broader: a valid stale fallback file or provider candidate can be accepted and then registered as the current plan. That is a P1 authority risk. Missing phase results, hardcoded attempt numbers, and unguarded cleanup are P1 status/evidence risks. No P0 is established by read-only inspection.

## Minimal generalized remediation

Consolidate on one decision-identity builder layered over `set_active_step`, `current_runner_incarnation`, and phase WBC. Initial admission must create a durable run ID and launch/version vector.

Use a provenance sidecar or metadata envelope for `prep.json`, triage/research/distill artifacts, and plan metadata so the public compatible prep payload need not change. Require the plan reader to verify the sidecar hash and exact current prep occurrence before prompt construction or blast-radius calculation; record that hash as the plan receipt’s upstream artifact.

Pass WBC dispatch into every prep substage and delete the prep call path that permits `wbc_dispatch=None`. Make `_finish_step` clear with `effective_run_id`; make phase-result emission fail closed and overwrite only for the current occurrence. Derive receipt attempt from active state/history.

Route all plan capture through the attested canonical parser. Remove or make unreachable Hermes’ and worker-level fallback parsers for plan, especially the unbound `plan_output.json` fallback.

## Required tests and retirement proof

Add deterministic tests for:

- concurrent old-plan completion versus replacement invocation: old completion cannot clear or overwrite current state;
- restart with stale `prep.json`, `phase_result.json`, and `plan_output.json`: all are rejected or quarantined;
- provider-specific malformed JSON, reasoning text, duplicate keys, and fallback output for Hermes/Codex/local strict mode;
- mutation of prep content, plan content/meta, source, config/profile, model/provider, and code/template version;
- two containers/PID namespaces and PID reuse: mismatched runner incarnation cannot resume, clear, or publish;
- initial state and every artifact requiring the complete identity envelope;
- plan receipt containing the exact prep hash and non-constant attempt.

Retirement proof must include static searches/tests asserting no prep call site invokes `run_step_with_worker` without WBC dispatch, no plan path calls `_parse_json_response` or `_extract_plan_capture_input` directly, no reader consumes raw `prep.json` except the canonical verifier, and no duplicate plan writer bypasses the shared identity-bearing writer.

## Unknowns

This was a read-only repository audit; cloud state, deployed wrappers, and historical artifacts were not inspected. It remains unknown whether an external deployment wrapper adds identity before invoking these paths. The repository-local direct call sites and schemas nevertheless prove the bypasses are reachable unless deployment prevents them, which is not enforced here.