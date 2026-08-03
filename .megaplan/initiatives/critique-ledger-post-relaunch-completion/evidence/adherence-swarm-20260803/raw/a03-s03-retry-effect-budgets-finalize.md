# a03-s03-retry-effect-budgets-finalize: retry-effect-budgets × finalize

## Verdict

FAIL. No occurrence-wide durable budget and idempotency boundary governs finalize model calls, provider fallback, schema repair, artifact publication, and replay.

The principal gap is P0 authority mutation: a restart or retry creates a new invocation identity and can regenerate/overwrite authoritative finalize artifacts without consuming the same durable occurrence budget. Secondary gaps are P1 artifact-side-effect duplication and status misreporting, plus P2 duplicate retry implementations.

I searched with `rg --files` and `rg -n` across `.megaplan`, `arnold`, `arnold_pipelines`, `tests`, and `docs` for `finalize`, `retry`, `repair`, `fallback`, `BudgetAuthority`, `EffectLedger`, `idempotency`, `current_invocation_id`, `capture_step_output`, `atomic_write_json`, `write_plan_artifact_json`, and boundary identifiers; I then line-inspected every matching caller and writer.

## Intended canonical contract

The repository contract requires retries to create a new attempt under the same semantic occurrence, reuse durable terminal/effect outcomes, and use a new generation only after explicit reconciliation and fresh admission (`.megaplan/initiatives/native-workflow-platformization/decisions/PLATFORM_CONTRACT.md:592-602`).

Resource accounting must remain eventwise bounded by admitted budget, including unresolved liabilities and reservations (`.megaplan/initiatives/native-workflow-platformization/decisions/PLATFORM_CONTRACT.md:641-654`). Every model/tool call must bind provider/model, schema, routing, token/cost/call/deadline budgets, cache identity, semantic occurrence, and attempt causality; accepted output and usage must be durable, with replay consuming the accepted result (`.megaplan/initiatives/native-workflow-platformization/decisions/PLATFORM_CONTRACT.md:865-874`).

The existing canonical side-effect implementation is `arnold/kernel/effect_ledger.py`: it prerecords intent, deduplicates idempotency keys, and forbids blind retry of indeterminate effects (`arnold/kernel/effect_ledger.py:1-11`, `:93-117`). However, no existing implementation combines that effect ledger with an occurrence-wide finalize retry/repair/delegation budget.

## Evidence and complete path inventory

The finalize caller is `handle_finalize`, which:

1. acquires the plan lock and writes critique clearance;
2. seeds scratch output and calls `_run_worker("finalize", ...)`;
3. promotes scratch or worker payload;
4. computes promotion evidence;
5. validates schema and semantics;
6. writes finalize artifacts;
7. applies the state projection; and
8. calls `_finish_step` (`arnold_pipelines/megaplan/handlers/finalize.py:2218-2361`).

Schema validation is centralized through `validate_payload_against_schema`, followed by semantic checks (`arnold_pipelines/megaplan/handlers/finalize.py:429-468`). Scratch classification/promotion is also centralized and expected-path-only (`arnold_pipelines/megaplan/handlers/structured_output.py:72-142`).

The worker path is `_run_worker` → `run_step_with_worker`, with phase WBC activation and worker dispatch (`arnold_pipelines/megaplan/handlers/shared.py:335-402`). `set_active_step` generates a fresh `current_invocation_id` on every invocation (`arnold_pipelines/megaplan/_core/state.py:1894-1963`). Phase WBC derives its attempt ID from plan path, step, and that invocation ID (`arnold_pipelines/megaplan/custody/phase_wbc.py:206-226`), then records start/completion in a per-plan SQLite ledger (`:244-318`, `:616-691`). The WBC facade is explicitly `ACTION_OFF` and `enforcement_enabled=False` (`:675-687`).

With the dispatcher flag off, the default path directly calls Hermes/Shannon/Codex workers (`arnold_pipelines/megaplan/workers/_impl.py:7094-7228`). Each provider path has its own local retry flag. With the dispatcher flag on, separate closure implementations repeat Codex/Shannon retry logic (`arnold_pipelines/megaplan/workers/_impl.py:6479-6542`, `:6545-6607`). Dispatcher requests carry step, plan path, and worker options, but no semantic occurrence, occurrence budget, or idempotency identity (`:7284-7299`; `arnold/agent/contracts.py:305-320`).

Hermes finalize is documented as a pure compiler with no tools (`arnold_pipelines/megaplan/workers/hermes.py:1189-1218`), so I found no current finalize delegation call. Global delegation exists elsewhere (`arnold/agent/toolsets.py:56-58`, `:199-202`), but it is not selected by this Hermes finalize path.

Model capture invokes `capture_step_output` with metadata containing provider/model/schema but no durable occurrence or budget fields (`arnold_pipelines/megaplan/workers/hermes.py:2387-2403`; `arnold_pipelines/megaplan/workers/shannon.py:2925-2954`). Generic structural repair is a one-shot recursive callback controlled only by in-memory `repair_attempt` (`arnold/pipeline/model_seam.py:1002-1012`, `:1115-1128`).

Finalize writes `task_feasibility.json`, `contract.json`, `finalize_snapshot.json`, markdown artifacts, and `finalize.json` (`arnold_pipelines/megaplan/handlers/finalize.py:2144-2166`). Only `finalize.json` goes through `write_plan_artifact_json`; the others use direct atomic writers. The handler comment identifies the feasibility report as the authoritative execute-entry receipt (`:2144-2146`).

## Adherence gaps

1. **P0 — authority mutation: no shared occurrence-wide budget/idempotency ledger.**

   Observed: provider retries are local (`arnold_pipelines/megaplan/workers/_impl.py:7141-7164`, `:7181-7228`), dispatcher retries duplicate that logic (`:6491-6542`, `:6586-6607`), and structural repair has an independent one-shot counter (`arnold/pipeline/model_seam.py:1003-1012`). Provider fallback is another loop (`arnold_pipelines/megaplan/workers/_impl.py:7305-7334`). `BudgetAuthority` is only called by loop-engine attribution, not finalize/worker dispatch (`arnold_pipelines/megaplan/loop/engine.py:108-139`; repository-wide search found no finalize or worker caller). Its key is `(lease_id, fencing_token)`, not semantic occurrence plus attempt (`arnold_pipelines/megaplan/runtime/budget_authority.py:1-15`, `:123-142`).

   Inference: after restart or retry, `set_active_step` creates a new invocation and therefore a new WBC attempt, while local retry/repair counters reset. A second model call and second artifact publication can therefore evade the first occurrence’s budget and idempotency history.

2. **P1 — authority mutation: artifact writers bypass the canonical typed/effect boundary.**

   Observed: `finalize.json` uses the PlanRepository writer, which validates typed envelopes when present (`arnold_pipelines/megaplan/store/plan_repository.py:238-287`, `:544-557`). `task_feasibility.json`, `contract.json`, `finalize_snapshot.json`, `user_actions.md`, and `final.md` bypass that seam with direct atomic writes (`arnold_pipelines/megaplan/handlers/finalize.py:2144-2166`). No finalize call records an effect intent through `EffectLedger`.

   Inference: a repeated finalize can rewrite artifact side effects without a stable artifact occurrence/effect key or durable prior-outcome check. Typed validation alone does not provide idempotent publication.

3. **P1 — status misreporting: promotion evidence is computed but not durable.**

   `build_promotion_evidence` is explicitly read-only (`arnold_pipelines/megaplan/handlers/structured_output.py:327-353`), and finalize only logs promotion states (`arnold_pipelines/megaplan/handlers/finalize.py:2289-2301`). The boundary contract requires receipts for `finalize_artifacts`, `finalize_fallback`, and `final_projection` (`arnold_pipelines/megaplan/workflows/boundary_contracts.py:1161-1230`). The normal finalize call supplies no `extra_boundary_ids`, so `_finish_step` cannot emit `final_projection` (`arnold_pipelines/megaplan/handlers/finalize.py:2348-2361`; `arnold_pipelines/megaplan/handlers/shared.py:900-902`, `:1011-1028`).

   The generic receipt writer is best-effort and suppresses failures (`arnold_pipelines/megaplan/handlers/shared.py:525-555`). This can report successful finalization while durable projection evidence is absent.

4. **P2 — duplicate retry/bypass implementations.**

   Legacy direct worker branches and dispatcher closures each implement provider retry policy (`arnold_pipelines/megaplan/workers/_impl.py:7094-7228`, `:6479-6607`). They are selected by an environment flag rather than one canonical policy. The generated producer matrix also remains stale, claiming no explicit finalize receipt producer (`arnold_pipelines/megaplan/workflows/contract_to_producer_matrix.json:303-309`).

## Incident reachability and severity

Observed reachability: finalize always creates a fresh invocation identity and can execute through either retry implementation. Artifact publication occurs after validation and mutates execute-entry inputs.

Inference: a provider timeout, malformed response, process crash after model acceptance, or two independently running containers can cause another model call and a second publication without occurrence-wide budget exhaustion or accepted-output replay. This is P0 when the regenerated task graph or feasibility result changes authority. Missing receipts are P1 status misreporting. Delegation is not currently reachable through Hermes finalize; its absence is negative evidence, not an additional current incident.

## Minimal generalized remediation

Add one durable finalize-occurrence record keyed by plan identity, semantic phase/occurrence, and generation. Admit the complete reserve before the first model call. Record each provider/repair attempt, accepted output/usage, fallback, artifact publication, and terminal/ambiguous result under stable idempotency keys.

Use the existing WBC/attempt ledger as lifecycle storage, but extend the dispatch/capture contract so `AgentRequest` and `StepInvocation` require occurrence, attempt, budget, provider, and idempotency metadata. Route all finalize providers through one retry facade; migrate callers, then delete the legacy branch and duplicate dispatcher closures. Route every authoritative artifact and receipt through one publication function using the same occurrence/effect identity. Persist promotion evidence and emit `final_projection`.

For migration, dual-record old and new identities, fail closed on disagreement, then retire the flag-selected paths and raw finalize writers. Prove retirement by repository-wide search showing no remaining finalize caller reaches the old retry helpers or direct artifact writers.

## Required tests and retirement proof

Add deterministic finalize tests covering:

- accepted model output replay after crash/restart with zero second provider call;
- retry and structural repair consuming one shared budget;
- provider fallback consuming the same reserve and failing closed at exhaustion;
- concurrent threads/processes and two containers/PID namespaces, with SQLite/flock uniqueness proving one publication per idempotency key;
- stale fencing/restart behavior;
- malformed or mutated scratch/artifact writes rejected or reconciled;
- indeterminate effect outcome never blindly retried;
- durable promotion evidence, `finalize_artifacts`, `finalize_fallback`, and `final_projection` receipts;
- negative delegation test proving finalize toolsets cannot delegate, plus envelope rejection if a future provider supplies tools.

Existing effect-ledger tests cover the canonical ledger in isolation (`tests/arnold/kernel/test_effect_ledger.py:93-117`), but repository searches found no test exercising finalize through a shared occurrence budget.

## Unknowns

The snapshot does not establish which provider/dispatcher flag is production-default in every deployment, nor whether any future finalize provider enables tools. It also does not prove whether all finalize artifact writes are classified as external effects; that classification should be made explicit in the publication contract.