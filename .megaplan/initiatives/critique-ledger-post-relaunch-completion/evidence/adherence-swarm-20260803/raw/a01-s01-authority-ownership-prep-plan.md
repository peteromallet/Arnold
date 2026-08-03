# a01-s01-authority-ownership-prep-plan: authority-ownership × prep-plan

## Verdict

Not conformant. The intended canonical state writer exists, but admission, initial-state creation, authority reads, bridge dispatch, and prep artifacts are not enforced through one unconditional owner.

Highest-risk gaps:

- P1 authority mutation: generic `megaplan run` bypasses init admission and can continue after initial-state persistence fails.
- P1 authority/status split: `state.json` is declared a projection but remains authority when R1 is disabled; several live callers read it directly.
- P1 status misreporting: malformed `prep.json` is converted into an empty blast-radius input.
- P1 status misreporting: bridge state-write failures are swallowed.
- P2 duplication: prep artifact writers and a prep-specific JSON parser duplicate canonical implementations.

## Intended canonical contract

The canonical live-state owner should be `_core.state.write_plan_state`, which locks, validates, atomically replaces `state.json`, and emits the state event record (`arnold_pipelines/megaplan/_core/state.py:1364-1382`, `1551-1577`). Authority readers should use `read_plan_state_cached(..., mode="authority")` (`arnold_pipelines/megaplan/_core/io.py:450-515`).

Initialization should be owned by `handle_init`, after `validate_admission_mutation` proves the registered writer, source record, and absence fence (`arnold_pipelines/megaplan/handlers/init.py:454-484`; `arnold_pipelines/megaplan/custody/admission_control.py:157-224`).

Prep and plan handlers should hold `load_plan_locked`, validate phase state, write validated artifacts, then persist lifecycle state through the canonical state writer (`arnold_pipelines/megaplan/handlers/plan.py:155-222`, `224-319`; `arnold_pipelines/megaplan/_core/state.py:867-897`).

Sidecars such as `prep.json`, receipts, and snapshots must remain projections. The repository already provides a centralized artifact API (`arnold_pipelines/megaplan/store/plan_repository.py:195-287`, `544-557`).

## Evidence and complete path inventory

I searched with `rg --files` and `rg -n` over `arnold_pipelines/megaplan`, `tests`, `scripts`, `docs`, and `evidence` for `prep`, `plan`, `admission`, `state.json`, `write_plan_state`, `save_state`, `atomic_write_json`, `capture_step_output`, `run_codex_prep_step`, and all relevant call sites; I inspected every material result with `nl -ba`.

Inventory:

- Initial-state writer: `handlers/init.py:485-623`; admission writer registration: `custody/admission_control.py:70-115`.
- Prep/plan callers and lifecycle consumers: `handlers/plan.py:75-110`, `155-319`; `_finish_step` persists state at `handlers/shared.py:880-1100`.
- Prep artifact writers: `handlers/shared.py:1118-1120`; `orchestration/prep_research.py:304-311`, `906-910`, `1079-1170`.
- Canonical artifact API: `store/plan_repository.py:195-299`, `544-557`.
- Canonical state readers/writers: `_core/io.py:450-515`; `_core/state.py:1364-1577`.
- Direct state readers: `runtime/inprocess_step.py:149-169`; `cli/run.py:322-340`; `cli/__init__.py:2301-2315`.
- Initial-state caller bypass: `cli/run.py:316-409`.
- Bridge caller/consumer: `runtime/bridge.py:359-380`, `527-566`; CLI invokes it at `cli/run.py:401-409`.
- Live prep provider path: `orchestration/prep_research.py:419-459` → `workers/_impl.py:6939-6990`, `7184-7198`.
- Duplicate but currently uncalled prep parser: `workers/_impl.py:6029-6043`; it is only exported by `workers/__init__.py:17-43`.

## Adherence gaps

1. **P1 — authority mutation: initialization is not transactional.**  
   **Observed:** `handle_init` creates the plan directory and writes `idea_snapshot.md` before constructing and persisting `state.json` (`handlers/init.py:485-515`, `609-623`). A crash or write failure leaves a directory/sidecar without canonical state. `active_plan_dirs` ignores such a directory, while the next init rejects it because `plan_dir.exists()` (`_core/state.py:301-320`; `handlers/init.py:454-459`).  
   **Inference:** restart can see “no plan” while a subsequent init is blocked by the orphaned sidecar directory.

2. **P1 — authority mutation/status: generic run bypasses admission and suppresses persistence failure.**  
   **Observed:** `cli/run.py` accepts arbitrary `--state`, creates the plan directory, and directly calls `write_plan_state(..., mode="replace")` without `validate_admission_mutation` (`cli/run.py:316-355`, `401-409`). `OSError` is caught and ignored at lines 403-406.  
   **Inference:** the pipeline may execute and report a result without durable initial authority. This is a second initial-state owner outside the registered init writer.

3. **P1 — authority/status: the projection/authority contract is conditional and bypassable.**  
   **Observed:** code declares `STATE_JSON_AUTHORITY = False` and calls `state.json` a sunset projection (`_core/state.py:79-104`), but authority reads fold WAL only when `r1_authority_on()` is true; otherwise they read `state.json` directly (`_core/io.py:473-510`). The flag inherits the master dispatch flag and defaults off when unset (`feature_flags.py:81-87`).  
   Live callers bypass the authority reader by parsing `state.json` directly: `runtime/inprocess_step.py:149-169`, `cli/run.py:322-340`, and `cli/__init__.py:2301-2315`.  
   **Inference:** a stale or corrupted projection can become authority for prep/plan status, especially across restart or provider/container boundaries.

4. **P1 — status misreporting: malformed prep input is treated as “no relevant code.”**  
   **Observed:** `_prep_relevant_code_surfaces` catches every exception from `prep.json` parsing and returns `[]` (`handlers/plan.py:75-92`). Plan generation then derives and persists blast-radius/state results (`handlers/plan.py:95-110`, `175-207`).  
   **Inference:** corrupt, missing, or schema-invalid prep evidence can produce a successful plan with an incorrectly narrowed test surface. No authority mutation is caused by the read itself, but the resulting plan mutation is semantically wrong.

5. **P2 — projection ownership duplication.**  
   **Observed:** the handler helper, orchestration helper, skip path, and repository API all independently write JSON artifacts (`handlers/shared.py:1118-1120`; `orchestration/prep_research.py:304-306`, `906-910`; `store/plan_repository.py:238-287`).  
   **Inference:** `prep.json` has multiple valid owners and inconsistent contract enforcement. This is not itself authority mutation, but `plan.py` consumes the sidecar as planning input.

6. **P2 — dead provider-specific duplicate.**  
   **Observed:** `run_codex_prep_step` has a separate parse/fail path that does not perform the generic repair retry (`workers/_impl.py:6029-6043`, `6139-6175`), while the live prep path uses `run_step_with_worker` and generic `run_codex_step`, whose recovery retry is at `workers/_impl.py:5769-5826`. Search found no production call to `run_codex_prep_step` beyond export.  
   **Conclusion:** not incident-reachable today, but it is a future bypass and should be retired.

7. **P1 — status misreporting: bridge persistence failure is swallowed.**  
   **Observed:** `MegaplanExecutorHooks.on_stage_complete` catches all exceptions from `write_plan_state` and does nothing (`runtime/bridge.py:359-380`). Additionally, `run_pipeline_dispatch` deletes `pipeline_key` and unconditionally routes to the bridge despite documentation describing a `demo_judges` allowlist (`runtime/bridge.py:527-566`).  
   **Inference:** a broad caller can run through a path that hides canonical-state failure and returns an in-memory result.

## Incident reachability and severity

The live prep path reaches generic provider recovery through `prep_research.py:419-437` and `_impl.py:7184-7198`; the dead `run_codex_prep_step` duplicate is therefore not the known JSON incident path.

The live malformed-`prep.json` fallback is reachable whenever a sidecar is absent, truncated, or invalid before `handle_plan`; it can silently alter planning scope. The CLI initial-state bypass and bridge path are reachable from `cli/run.py:401-409`. The initialization orphan requires a failure between directory creation and `save_state`, so it is restart/crash dependent.

## Minimal generalized remediation

- Add one `create_initial_plan` owner that performs admission, stages snapshot and state, and publishes the plan directory only after canonical state is durable. Use it from `handle_init` and `cli/run`; remove the CLI `OSError` swallow. Retire orphan directories deterministically on restart.
- Make the selected authority unconditional for this surface: enable/fail closed on R1, or explicitly retain `state.json` as authority. Remove raw `state.json` reads from live callers and route them through `read_plan_state_cached`.
- Make malformed/missing `prep.json` fail closed with a structured parse/status failure; never substitute an empty planning floor.
- Consolidate prep artifact writes on `PlanRepository.write_artifact_json` (with one hash wrapper), then delete `_artifact_json`, `write_skip_prep_artifacts`’s direct writes, and the dead `run_codex_prep_step` export/function.
- Enforce the bridge allowlist or remove the unused `pipeline_key` contract; persistence errors must propagate.

## Required tests and retirement proof

- Concurrent init/run attempts, including two processes sharing one plan directory, must yield one admitted owner and one durable state.
- Crash/restart injection between directory creation, snapshot write, and state write must leave no discoverable orphan or must deterministically recover it.
- With R1 on and off, divergent WAL/cache fixtures must produce one authority result; direct readers must be covered.
- Malformed provider output for triage/distill must exercise canonical recovery, provider fallback, and “no phase success before validated payload.”
- Corrupt/missing `prep.json` must fail closed; valid skip and normal prep must use the same writer.
- Test state-write failure cannot produce a successful CLI/bridge result.
- Test plan locking with concurrent processes on the same filesystem, plus two containers/PID namespaces sharing that filesystem; the `flock` contract is at `_core/state.py:867-888`.
- Retirement proof: static `rg` finds no calls to deleted writers/parser, `run_pipeline_dispatch` rejects non-allowlisted keys, and all current state readers appear in the authority-reader audit.

## Unknowns

No services, cloud state, or tests were run. I did not verify deployment values for `R1_AUTHORITY` or `MEGAPLAN_UNIFIED_DISPATCH`. The exact external Critique incident trace was not used; reachability conclusions above are from repository call graphs and are marked as inference where applicable.