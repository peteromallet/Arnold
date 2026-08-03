# a02-s02-identity-version-provenance-critique-revise-gate: identity-version-provenance × critique-revise-gate

## Verdict

Nonconformant. The boundary has a P0 authority gap: critique and force-proceed custody validate artifact hashes and iteration, but not run, invocation/attempt, runner incarnation, version set, provider, or launch provenance. Stale evidence can therefore be internally consistent yet belong to another execution boundary.

A second P0 is the gate’s direct historical-critique readers bypassing custody. Additional P1 status/authority gaps exist in scratch recovery, schema-parity handling, and finalize projection fallback. A partial canonical identity implementation exists in RuntimeEnvelope and phase WBC, but no single enforced contract joins it to critique custody or force-proceed authority.

## Intended canonical contract

Every critique, gate, revise, clearance, and force-proceed decision should carry and validate one exact identity:

- `run_id`, plan/run artifact root, and pipeline manifest identity from RuntimeEnvelope (`arnold_pipelines/megaplan/cli/run.py:656-704`).
- `invocation_id`, attempt ordinal, selected provider/model/session, and runner incarnation from `set_active_step` (`arnold_pipelines/megaplan/_core/state.py:1894-1963`).
- Exact phase-WBC `attempt_id`, graph/iteration revision, code/config/template versions, and actor/tool provenance from `_event` (`arnold_pipelines/megaplan/custody/phase_wbc.py:722-765`).
- Immutable artifact hashes and causal predecessors.

Phase WBC is the closest canonical identity carrier: it defines critique→gate, gate→revise, and revise→critique surfaces (`arnold_pipelines/megaplan/custody/phase_wbc.py:70-92`) and derives attempts from plan path, step, and invocation (`:206-212`). However, its facade is explicitly evidence-only (`:675-687` in the same file); authority must remain CAS state plus custody validation. The missing piece is an enforced join between those systems.

## Evidence and complete path inventory

I searched with `rg --files` and `rg -n` across `arnold_pipelines/megaplan`, `arnold`, `tests`, `docs`, schemas, wrappers, and call sites for `critique`, `revise`, `gate`, `force-proceed`, `custody`, `run_id`, `attempt_id`, `invocation_id`, `provider`, `incarnation`, and artifact names including `critique_v*`, `critique_output.json`, `gate.json`, and `gate_carry.json`. I then inspected all relevant matches with `nl -ba`.

Writers and authority callers:

- Critique writes raw output, `critique_vN.json`, custody receipt, registry updates, and CRITIQUED state (`arnold_pipelines/megaplan/orchestration/critique_runtime.py:940-1003`).
- `write_critique_production_receipt` writes hashes, findings, IDs, iteration, and admission (`arnold_pipelines/megaplan/orchestration/critique_custody.py:221-304`).
- Gate validates custody, builds gate signals, then writes gate artifacts (`arnold_pipelines/megaplan/handlers/gate.py:90-120`; `:1170-1174`).
- Revise invokes a worker for the next iteration and writes the new plan version (`arnold_pipelines/megaplan/orchestration/critique_runtime.py:1533-1547`; `:1578-1604`).
- Force-proceed builds custody, CAS-commits it into state, then projects registry, debt, gate, and carry artifacts (`arnold_pipelines/megaplan/planning/control_binding.py:646-710`; `:1067-1101`; `:1659-1681`; `arnold_pipelines/megaplan/orchestration/force_proceed_custody.py:136-223`).

Readers and consumers:

- Canonical gate admission is `validate_gate_input_custody` (`arnold_pipelines/megaplan/orchestration/critique_custody.py:396-428`).
- Bypass readers directly load critique history in gate signals (`arnold_pipelines/megaplan/orchestration/gate_signals.py:74-85`, `:152-160`), gate prompts (`arnold_pipelines/megaplan/prompts/gate.py:305-321`), iteration audit (`arnold_pipelines/megaplan/audits/iteration.py:21-38`), and iteration pressure (`arnold_pipelines/megaplan/orchestration/iteration_pressure.py:21-38`).
- Scratch recovery reads unversioned `critique_output.json` (`arnold_pipelines/megaplan/orchestration/critique_runtime.py:1065-1078`).
- Finalize and North Star consumers read `gate_carry.json`/`gate.json` directly (`arnold_pipelines/megaplan/handlers/finalize.py:1617-1715`; `arnold_pipelines/megaplan/north_star_actions.py:600-655`).
- Auto gate recovery uses current iteration, hashes, and mtime ordering but not full identity (`arnold_pipelines/megaplan/auto.py:3062-3188`).

## Adherence gaps

1. **P0 — authority mutation: custody is not identity-bound.**  
   The critique receipt contains iteration, plan/critique/raw hashes, findings, and admission, but no run, invocation, attempt, incarnation, provider, manifest, code/config, or launch identity (`arnold_pipelines/megaplan/orchestration/critique_custody.py:274-303`). Validation checks only local files, hashes, IDs, and losslessness (`:307-393`); gate admission adds only registry membership (`:396-428`). Force-proceed custody similarly uses only plan ID, state, reason, and dispositions (`arnold_pipelines/megaplan/orchestration/force_proceed_custody.py:87-100`). Its projection mutates flag authority, debt, gate, and carry (`:161-223`).

   **Observed:** the required identity fields are absent from the authoritative records.  
   **Inference:** after restart or same-directory reuse, a stale receipt/custody row whose local files and digests agree can pass and mutate current gate/registry/debt state.

2. **P0 — authority mutation: direct historical readers bypass canonical custody.**  
   `build_gate_signals` reads current and prior critiques directly (`gate_signals.py:74-85`, `:152-160`); prompts and audit/pressure code scan `critique_vN.json` directly (`prompts/gate.py:305-321`; `audits/iteration.py:21-38`; `orchestration/iteration_pressure.py:21-38`). Those values feed the gate worker and the handler persists the resulting route/gate artifact (`handlers/gate.py:106-120`, `:1170-1174`).

   **Observed:** these consumers do not call `validate_gate_input_custody`.  
   **Inference:** tampered or stale historical critique can influence a PROCEED/ITERATE authority decision even when the current receipt is valid.

3. **P1 — authority mutation: stale scratch recovery.**  
   `_recover_valid_critique_output` accepts any structurally valid unversioned `critique_output.json` (`critique_runtime.py:1065-1078`). The recovered payload is then persisted as the canonical iteration artifact and updates the flag registry (`:952-998`). No current invocation, attempt, provider, or launch binding is checked.

4. **P1 — status misreporting and possible authority drift: schema parity fails open.**  
   Gate catches `SchemaParityError`, records metadata, and explicitly does not block the gate (`handlers/gate.py:1233-1246`). This permits a gate to report a successful route while its schema contract is known to be divergent.

5. **P1 — authority/status mutation: finalize projection preserves unbound decisions.**  
   Finalize reads prior gate/carry content and copies accepted tradeoffs, settled decisions, and North Star actions into a newly written gate/carry projection (`handlers/finalize.py:1617-1670`, `:1705-1715`). The reader validates shape, not custody identity (`north_star_actions.py:617-655`).

6. **P2 — canonical identity exists but is bypassed.**  
   Active-step state records attempt, invocation, provider/model, runner incarnation, and lease (`_core/state.py:1918-1962`); phase WBC records identity/version/provenance (`custody/phase_wbc.py:734-762`). Critique custody and force custody never reference these records. This is a consolidation failure, not evidence that WBC itself is missing.

## Incident reachability and severity

The P0 path is:

`stale critique/force input → local hash/iteration validation → gate or force-proceed artifact → registry/debt/state mutation`.

The claim that this is reachable across restart, provider retry, or two containers is an inference from the missing comparisons, not an observed production replay. It is nevertheless credible: active execution identity changes across invocations, while artifact validation remains directory-local. Provider/model/fallback metadata is stored in active state (`_core/state.py:1942-1952`) but omitted from custody. Foreign PID namespaces are correctly classified as unknown unless leased (`_core/phase_runtime.py:204-245`), yet custody does not require that liveness/incarnation evidence.

Existing tests prove content custody and CAS idempotence, not boundary identity: `tests/orchestration/test_critique_custody.py:167-186` and `tests/arnold_pipelines/megaplan/test_force_proceed_custody.py:89-210`.

## Minimal generalized remediation

Add one shared `DecisionIdentity` envelope and validator, populated from RuntimeEnvelope, active-step state, and exact phase-WBC attempt/version. Add it to critique receipts, clearance/final binding, gate signals/carry, and force-proceed custody.

Then:

- Make gate admission require exact identity equality before any worker dispatch or route mutation.
- Make force-proceed projection require identity equality before flag/debt/gate writes.
- Route all historical critique consumers through canonical custody readers; delete direct artifact reads.
- Remove unversioned scratch recovery, or require a current-invocation scratch receipt with matching hash and provider provenance.
- Replace auto-recovery mtime checks with identity plus hash checks.
- Treat existing artifacts without the new envelope as legacy/untrusted and require reacquisition.

This is narrower than a rewrite: it adds one validator and threads one envelope through existing custody/WBC/CAS boundaries.

## Required tests and retirement proof

Deterministic tests must cover:

- Each mismatch independently: run ID, invocation/attempt, ordinal, iteration/plan hash, manifest/code/config/template, provider/model/session, runner incarnation, PID namespace, and launch provenance. Every mismatch must fail closed with no state, registry, debt, gate, or carry mutation.
- Concurrent gate and force-proceed callers, CAS conflict, duplicate retry, and crash between CAS and projection.
- Restart with a new invocation; stale scratch/receipt must be rejected.
- Provider fallback and reprompt paths; only the selected provider/session’s result may be admitted.
- Mutation of raw critique, critique, plan, custody, clearance, gate, or carry after creation; mtime changes alone must never establish freshness.
- Two-container/PID-reuse cases using the existing incarnation model; unknown foreign namespace must not proceed.
- Full WBC lifecycle for critique, gate, and revise, asserting identity/version equality with custody.

Retirement proof must include an `rg`-based allowlist test showing no production direct reads of `critique_v*`, `critique_output.json`, `gate.json`, or `gate_carry.json` outside canonical readers. Delete the bypass functions/call sites rather than wrapping them. Add a test that monkeypatches raw artifact reads to raise and proves every gate/prompt/audit/finalize path still works through custody.

## Unknowns

- Whether external wrappers copy or reuse plan directories outside this repository.
- The exact deployed provider/launch provenance fields available to phase-WBC adapters.
- Whether `critique_output.json` is always cleared before every worker invocation.
- Whether legacy `critique.json` consumers remain reachable through wrappers not found under the searched repository roots.
- Whether all auto-recovery callers enforce the current active invocation before entering `auto.py:3062-3188`.