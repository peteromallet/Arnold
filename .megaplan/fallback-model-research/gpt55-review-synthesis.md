# GPT-5.5 Review Synthesis

Date: 2026-07-04
Inputs:
- `.megaplan/fallback-model-research/model-fallback-design.md`
- `.megaplan/fallback-model-research/results/gpt55-sense-check.txt`
- `.megaplan/fallback-model-research/results/gpt55-trigger-sweep.txt`

## Verdict

The design direction is sound but not implementation-ready. The main correction is that ordered fallback cannot be treated as a small worker-level retry loop alone. The scalar model-spec contract is spread across profile parsing, policy rewrites, persisted `phase_model`, tier maps, state validation, override/control paths, execute batch routing, adaptive critique, worker fanout, cloud/chain preflight, and observability.

Keep the core judgment:

- User-facing syntax should be TOML arrays, not comma-delimited strings.
- Fallback is for availability/infrastructure failures, not quality repair.
- Do not break `AgentMode.__iter__`.
- Configured fallback chains must take precedence over ambient `detect_available_agents()` fallback.

## Required Design Changes

1. Make one canonical internal representation decision. Do not leave the design split between `FallbackSpecChain` objects and encoded strings. Recommendation: use a `FallbackSpecChain` helper at routing boundaries, and encode only where persisted `phase_model` requires a string.

2. Add a scalar-compatibility inventory to the design before implementation. Required surfaces:
   - profile loaders and validators
   - `tier_models`
   - `profile_to_phase_models`
   - `state.config.phase_model`
   - `_validate_persisted_phase_models`
   - override/control binding
   - execute batch routing
   - adaptive critique routing
   - `WorkerUnit` / parallel critique / prep fanout
   - routing ledger, receipts, active step, history, status view
   - cloud preflight and chain milestone parsing

3. Replace the simple “centralized loop in `run_step_with_worker`” plan with a two-layer design:
   - resolve fallback chains before creating scalar `AgentMode`
   - execute ordered attempts in worker dispatch
   - enforce execute-specific mutation/output guards in `execute/batch.py`

4. Define a backend-normalized retryability classifier. It should map `CliError.code`, provider status, and error payloads to:
   - retryable infrastructure
   - permanent configuration/auth
   - semantic/model-output failure
   - execute-unsafe after-output failure

5. Expand tests beyond parser and simple worker retry. Add state resume, override, cloud/chain, parallel critique, prep fanout, and execute dirty-tree/output-boundary tests.

## Trigger Policy

Move to the next spec only when all are true:

1. The current attempt failed before an accepted phase payload/result boundary.
2. The failure is classified as availability or infrastructure.
3. Any existing same-spec local recovery has already run.
4. The next spec is explicitly listed in the selected chain.
5. The next route plausibly has independent capacity, auth, quota, provider, executable, or transport.

Retryable triggers:

- `codex_pre_first_byte_stall`
- `worker_stall`
- `worker_timeout`, only if no accepted structured output/recovery exists
- `connection_error`
- provider 429 / rate limit
- provider 5xx / transient API failure
- quota or usage limit exhaustion only when the next route uses independent quota/auth
- missing executable/dependency for one route only when another explicit route is viable
- context overflow only behind an explicit opt-in flag

Never trigger fallback on:

- invalid profile syntax or malformed fallback specs
- unknown/unsupported model
- missing dependencies/auth for every configured route
- same-provider auth failure when the next spec uses the same auth path
- HTTP 400 / invalid request
- generic `worker_error` unless reclassified as transient infrastructure
- malformed model output, JSON repair failure, schema validation failure
- model structural audit failure
- legitimate `blocked`, `failed`, `pending`, `needs_rework`, gate escalation, or review rejection
- execute task/evidence/test failures
- human approval/preflight/destructive-action blocks
- cost caps, budget exhaustion, or auto-driver iteration caps

## Phase Scope

Fallback should apply:

- centrally for `plan`, `revise`, `gate`, `finalize`, `loop_plan`, normal `review`, and normal `critique`
- per prep stage for `prep-triage`, `prep-research`, `prep-distill`
- per unit for prep research fanout
- per check/unit for adaptive/parallel critique within the selected complexity tier chain
- per side for `tiebreaker_researcher` and `tiebreaker_challenger`
- technically for `feedback`, but exhausted fallback should preserve best-effort feedback behavior
- for `execute` and `loop_execute` only under strict pre-output/no-accepted-result rules

Fallback should not apply as a separate outer mechanism in cloud, chain, bakeoff, supervisor, or auto-driver. Those layers should preserve/pass chains and let child phase dispatch decide.

## Execute Policy

Execute fallback is the riskiest part. Treat `loop_execute` the same as `execute`.

Allow automatic fallback only for:

- pre-first-byte failures
- connection/open failures
- rate limit / quota failures before output
- timeout where timeout recovery proves no completed batch result was accepted

Do not fallback after:

- task updates exist
- `execution_batch_*.json` or equivalent structured output was accepted
- timeout recovery accepted a result
- evidence audit ran on produced output
- git/tree mutation cannot be proven harmless

Fallback attempts for Codex execute should use fresh sessions.

## Open Owner Decisions

- Should context overflow fallback be opt-in only? Recommendation: yes.
- Should execute fallback ever proceed after possible mutation without a clean reset? Recommendation: no.
- Should extreme parallel review be allowed to fall back to single Codex/Claude review and change topology? Recommendation: no for v1.
- Should first-route missing credentials fail preflight or skip at runtime? Recommendation: fail preflight unless an explicit flag allows skip.
- Should fallback lists be profile-only v1 or also CLI-expressible? Recommendation: profile-only v1.
- Should `prep_models` support fallback arrays in v1? Recommendation: yes if prep stage routing is touched anyway.

## Updated Risk Estimate

Risk is high but bounded. Expect 2-4 focused engineering days for a profile/tier fallback v1 with real tests if execute fallback is limited to pre-output/provider-open failures. Including mid-timeout execute fallback with dirty-tree safety would push it beyond that.
