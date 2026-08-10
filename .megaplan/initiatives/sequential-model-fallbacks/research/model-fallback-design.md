# Sequential Model Fallbacks for Megaplan Profiles

Date: 2026-07-04
Status: revised design recommendation after DeepSeek, GPT-5.5, and six targeted DeepSeek audits
Scope: Megaplan profile routing, tier routing, worker dispatch, and observability

> **2026-07-11 scope note:** This document remains the historical detailed design for the fallback layer. The initiative now targets the broader unified managed-agent contract in `NORTHSTAR.md`. Sprint 1's fallback-safety track must preserve these scalar/array, provider-family, observability, and quality-vs-availability rules while applying one classifier to Megaplan and resident-managed dispatchers. Its newer locked safety rule is stricter: any dispatcher, including execute, may advance only with affirmative no-mutation evidence; ambiguity fails closed. See `decisions/managed-agent-contract-boundaries.md`.

## Goal

Allow a profile or tier entry to declare an ordered list of model specs. At runtime, Megaplan should try the first spec and move to the next only when the attempt fails for an availability or infrastructure reason.

Example target shape:

```toml
[profiles.partnered-5.tier_models.execute]
4 = ["codex:gpt-5.4", "codex:gpt-5.5", "hermes:deepseek:deepseek-v4-pro"]
5 = ["codex:gpt-5.5", "codex:gpt-5.4", "hermes:deepseek:deepseek-v4-pro"]
```

Equivalent phase-level usage should also be allowed:

```toml
[profiles.resilient]
plan = ["codex:gpt-5.5:high", "codex:gpt-5.4:high", "hermes:deepseek:deepseek-v4-pro"]
execute = "codex:gpt-5.5"
```

The fallback chain is ordered. It is not a load-balancer, roulette wheel, or quality ensemble.

## Non-Goals

- Do not retry on bad reasoning, low-quality output, failed tests, schema validation failures, or legitimate `blocked` results.
- Do not hide structural configuration errors such as malformed model IDs or missing auth for every configured provider.
- Do not change profile names or existing single-string profile behavior.
- Do not break the existing `AgentMode.__iter__` four-value compatibility contract.
- Do not make comma-delimited strings part of the user-facing syntax.

## Design Position

Use **native TOML arrays** as the user-facing syntax and normalize internally to a `FallbackSpecChain` helper. Keep that object or a typed equivalent through routing-aware code. Encode only at unavoidable string-only boundaries such as persisted `phase_model` entries.

I would not use comma-delimited strings. Provider model names already contain colons, slashes, hyphens, dots, and sometimes account paths. A comma delimiter is a latent parsing bug and makes it harder to emit useful profile validation errors. TOML arrays are explicit and order-preserving.

I would also avoid pushing fallback state into the positional `AgentMode` tuple. `AgentMode.__iter__` currently unpacks as `(agent, mode, refreshed, model)` and is used across handlers. Add named optional fields only if needed, and keep old unpacking behavior untouched.

## Data Model

Add a small helper module, likely `arnold_pipelines/megaplan/model_fallback.py`, with:

```python
@dataclass(frozen=True)
class FallbackSpecChain:
    specs: tuple[str, ...]

    @property
    def primary(self) -> str: ...

def normalize_fallback_specs(raw: str | list[str] | tuple[str, ...]) -> FallbackSpecChain: ...
def is_fallback_chain(raw: object) -> bool: ...
def encode_fallback_chain(chain: FallbackSpecChain) -> str: ...
def decode_fallback_chain(value: str) -> FallbackSpecChain: ...
def provider_family(spec: str) -> str: ...
```

The helper must validate each element with `parse_agent_spec`, reject empty lists, reject non-string members, and reject unresolved `premium` placeholders after policy expansion.

For string-only persistence, use a deliberately explicit internal JSON prefix:

```text
__fallback_json__:["codex:gpt-5.5","codex:gpt-5.4"]
```

The encoding must be canonical compact JSON: `__fallback_json__:` plus `json.dumps(specs, separators=(",", ":"), ensure_ascii=True)`. `phase_model` remains `list[str]` only; multi-spec phase values are encoded as `phase=<encoded-chain>`. Chain YAML and cloud-upload normalization must preserve encoded strings exactly and should not introduce raw nested arrays inside `phase_model`.

Do not spread raw `list | str` checks across the codebase. Profile parsing should normalize once, then routing code should pass `FallbackSpecChain` or decode from the canonical persisted string. `decode_fallback_chain(value)` must also accept a plain scalar string and return a one-spec chain so old persisted state remains valid.

## Scalar Compatibility Inventory

This feature is risky because single model specs are assumed in more places than profile loading. The implementation must update or explicitly preserve all of these surfaces:

- `profile_to_phase_models`
- `state.config.phase_model`
- `state.config.tier_models`
- `state.config.prep_models`
- `_validate_persisted_phase_models`
- override handlers and planning control binding
- execute batch tier resolution
- adaptive critique tier resolution
- prep model resolver and prep fanout
- `WorkerUnit` fanout paths
- routing ledger and batch routing records
- receipts, history entries, active step, and status/introspection views
- cloud preflight, cloud chain launch, and chain milestone parsing
- local/runtime preflight (`arnold_pipelines/megaplan/preflight.py`)
- cloud CLI phase-model materialization (`arnold_pipelines/megaplan/cloud/cli.py`)
- init state config persistence (`arnold_pipelines/megaplan/handlers/init.py`)
- bakeoff/profile archival surfaces
- calibration ledger tier projection
- routing identity/cache keys
- `_agent_requested_explicitly`
- `_vendor_adjusted_default_spec`
- `_canonicalize_tier_models_for_json`
- `_validate_resolved_profile_invariants` and `_validate_named_profile_invariants`
- `_resolve_with_inheritance`
- `resolve_prep_models`

Any encoded fallback chain that reaches one of these surfaces must be decoded by a shared helper before calling `parse_agent_spec`. Any serialization or cache identity that must remain scalar should use the selected/actual attempt, not the whole configured chain.

## Profile Parsing

Touch points:

- `arnold_pipelines/megaplan/profiles/__init__.py`
- `arnold_pipelines/megaplan/profiles.py`
- `arnold_pipelines/megaplan/profiles/policy.py`

Required changes:

1. `_validate_profile_map` should accept a string or `list[str]`.
2. `_extract_tier_models` / `_validate_tier_models` should accept string or `list[str]` tier values.
3. `_validate_prep_models` / `resolve_prep_models` should accept string or `list[str]` prep-stage values.
4. Policy rewrites must map over every element in a fallback chain:
   - vendor rewrite
   - depth rewrite
   - critic rewrite
   - available model floor
   - DeepSeek provider rewrite
5. Profile inheritance and canonical JSON serialization must preserve arrays without concatenating unrelated parent/child chains.
6. `profile_to_phase_models` must preserve fallback chains when it emits `phase=spec` entries, or it must emit a canonical encoded form that `resolve_agent_mode` can decode.

Backwards compatibility rule: every existing single-string profile should produce exactly the same effective routing as before.

## Routing and Runtime Dispatch

Ordered fallback needs two layers:

1. A chain-resolution layer before scalar `AgentMode` creation. This layer chooses the configured chain for the phase, tier, prep stage, fanout unit, or critique check.
2. An attempt layer near `run_step_with_worker` that iterates over resolved specs, invokes the correct backend, classifies failures, records attempts, and returns the first successful worker result.

`run_step_with_worker` is still the main dispatch choke point, but it is not sufficient by itself. Execute batch routing, adaptive critique, prep fanout, and any code that constructs `AgentMode` ahead of time must pass a chain rather than a single already-resolved mode.

`run_step_with_worker` already resolves the agent, invokes Hermes/Shannon/Codex, records routing, and has a narrow existing runtime fallback for non-explicit agents on `auth_error` / `connection_error`. The new configured chain should take precedence over that ambient fallback. Ambient `detect_available_agents()` fallback should remain legacy behavior only when no explicit fallback chain is configured.

Proposed behavior:

1. Resolve the selected phase/tier spec into a chain.
2. For each spec in order:
   - parse into agent/model/effort
   - resolve default concrete model for Codex/Claude where necessary
   - set active step model to the currently attempted spec
   - invoke the worker
   - on success, record selected index and return
   - on retryable infrastructure failure, record attempt failure and continue
   - on non-retryable failure, raise immediately
3. If all specs fail retryably, raise a `CliError` that includes the complete attempt list.

This should live below handler code so plan, critique, review, finalize, execute, loop phases, and future phase callers get one behavior.

Exception: execute safety gates must live around the execute batch boundary because only `execute/batch.py` can know whether structured output, timeout recovery, or tree mutation has crossed the accepted-output boundary.

## Retryability Classifier

Add a backend-normalized classifier instead of embedding string checks in each loop:

```python
class FallbackDecision(Enum):
    RETRY_NEXT_SPEC = "retry_next_spec"
    RAISE_PERMANENT = "raise_permanent"
    RAISE_SEMANTIC = "raise_semantic"
    RAISE_EXECUTE_UNSAFE = "raise_execute_unsafe"
```

Inputs should include `CliError.code`, provider status code, provider error kind, raw worker metadata, phase, whether output was accepted, whether any execute mutation/structured output was observed, and whether context fallback is enabled.

This classifier must cover Codex, Shannon/Claude, Hermes, prep fanout, and existing ExternalError payloads. A generic `worker_error` should not move down unless it has been reclassified as transient infrastructure.

The classifier must compare provider families for auth, balance, quota, and likely rate-limit failures. Add a real `provider_family(spec)` helper rather than encoding this in prose:

- `codex:*` -> `codex`
- `claude:*` / `shannon:*` -> `claude`
- `hermes:<provider>:...` -> `hermes:<provider>`
- unresolved bare/unknown Hermes provider -> permanent configuration error unless it is resolved before classification

A Codex quota failure can move to a Hermes/DeepSeek spec, but should not move to another Codex spec. Hermes sub-providers with distinct key pools can be treated as independent families. Same-provider auth failures are permanent configuration failures, not fallback triggers.

## Trigger Policy

Fallback should trigger only for failures where a different model/provider can plausibly change availability:

- `worker_timeout`
- `worker_stall`
- `codex_pre_first_byte_stall`
- `connection_error`
- provider rate limit / 429
- provider 5xx / transient transport errors
- provider quota or usage limit exhaustion when the next provider/model may have independent quota
- context exhaustion only if explicitly allowed by a policy flag such as `fallback_on_context_exhaustion = true`

Fallback must not trigger for:

- invalid profile syntax
- unknown agent or unsupported model
- missing dependencies for every configured route
- auth errors for the same provider family unless the next spec uses a distinct provider/auth path
- malformed model output
- JSON/schema validation failure
- model structural audit failure
- legitimate `blocked`, `failed`, or `pending` task result
- test failures after code was changed
- execution evidence failures

Reasoning: fallback is an availability feature. It is not a correctness repair loop.

## Execute and Idempotency

Execute is the risky phase because workers may mutate the tree. The current execute flow selects a tier around `execute/batch.py`, calls `_run_and_merge_batch`, captures payload, merges task updates, writes `execution_batch_*.json`, rewrites `finalize.json`, runs evidence validation, and records history. There is no broad safe point after worker invocation where Megaplan can assume no accepted output or tree mutation occurred.

Judgment call after the execute safety audit: **automatic execute fallback is out of scope for v1**. V1 should still parse, validate, preserve, and preflight execute fallback chains, but dispatch should classify execute fallback as unsafe and raise a clear `RAISE_EXECUTE_UNSAFE`/`CliError` rather than moving to the next model.

V1 execute semantics are primary-only. Megaplan may attempt spec index `0` for `execute`/`loop_execute`. If that attempt fails with an otherwise retryable infrastructure error and the chain has spec index `>0`, it must raise an explicit `execute_fallback_unsafe` error that records the attempted spec and the blocked next specs. It must not silently ignore the rest of the chain, flatten the chain to the primary, or attempt the second spec.

V2 can add execute fallback only after explicit no-output/no-mutation telemetry exists. The first acceptable V2 scope would be pre-first-byte or provider-open failures:

- `codex_pre_first_byte_stall`
- connection/open failure before worker output
- provider 429 / quota / 5xx before output
- timeout only if timeout recovery proves no checkpoint, accepted structured result, evidence audit, merge, or git mutation exists

Treat `loop_execute` exactly like `execute`.

## Tier Routing

`tier_models.execute` and `tier_models.critique` should support fallback chains per tier.

Example:

```toml
[profiles.partnered-5.tier_models.critique]
4 = ["claude:claude-sonnet-4-6", "hermes:deepseek:deepseek-v4-pro"]
5 = ["claude:claude-opus-4-7", "codex:gpt-5.5:high", "hermes:deepseek:deepseek-v4-pro"]
```

The tier selector still chooses one tier from complexity. Fallback only operates within that tier's configured chain. It must not step down to a lower tier unless the profile author explicitly lists that lower-tier model in the chain.

## CLI and Overrides

Profile fallback chains should not make explicit overrides surprising.

Rules:

- `--phase-model execute=codex:gpt-5.4` remains a single explicit route and suppresses `tier_models.execute` as it does today.
- Optional later extension: allow repeated `--phase-model` for the same phase to express an ordered chain, but do not add that in the first cut.
- `override set-model` should set a single model and clear tier routing for that phase, preserving current semantics.
- A future `override set-fallback-models --phase execute --model A --model B` can be added once the base feature is stable.

## Observability

Every fallback-capable dispatch should record:

- `configured_specs`: full ordered chain
- `attempted_specs`: specs actually attempted
- `selected_spec`: spec that succeeded
- `selected_index`: zero-based index
- `fallback_triggered`: boolean
- `fallback_reasons`: one reason per failed attempt
- `actual_model`: provider-reported model when available
- `attempt_costs`: optional, only if cost attribution is available per failed attempt

Places to update:

- routing ledger
- receipts
- active step state
- history entries
- status view
- audit query/reporting

Do not replace scalar `model` immediately. Add list fields alongside it and let old readers keep working. Encoding is only for string-only persistence surfaces; JSON observability records should store arrays as arrays.

Legacy scalar `model`, `selected_spec`, cache identity, and session identity should represent the selected/actual attempt, not the full configured chain.

## Prep, Fanout, Review, and Tiebreakers

Fallback applies beyond the main linear phases:

- `prep-triage`, `prep-research`, and `prep-distill` should support chains per prep stage.
- Prep research fanout should fallback per research unit. If the chain exhausts, preserve the current sentinel/error-finding behavior.
- Adaptive critique should fallback per check/unit and only within the selected complexity tier chain.
- `critique_evaluator` can fallback on infra failure, but invalid evaluator output is not a fallback trigger.
- Normal review can use central fallback.
- Extreme/parallel review can fallback per unit only if the review topology stays compatible. Falling from a parallel Hermes topology to one single Codex/Claude review is out of scope for v1.
- `tiebreaker_researcher` and `tiebreaker_challenger` fallback independently. Local synthesis and human decision steps do not fallback.
- `feedback` can technically fallback, but exhausted fallback should preserve best-effort feedback behavior and not fail the plan.

Thread this through fanout with a sidecar such as `WorkerUnit.fallback_chain`, not by adding positional fields to `AgentMode`. The field must survive all `WorkerUnit` constructors, repair-unit cloning, and process pack/unpack paths.

## Cloud, Chain, Bakeoff, and Auto-Driver

Cloud and chain surfaces must preserve encoded fallback chains instead of flattening them to the first spec.

Minimum requirement:

- chain milestone `phase_model` accepts `phase=[specs...]` only if the YAML parser can preserve it, otherwise keep chain fallback behind profile files first.
- cloud and local/runtime preflight should walk every spec in every chain and report missing credentials, runtime commands, and provider requirements for every provider that might be used.
- cloud CLI materialization from preflight summaries back into chain specs must preserve encoded fallback values and must not flatten them to the primary spec.
- bakeoff does not need a new dimension. Fallback is internal to a profile. If the operator wants to compare fallback policies, they can create separate profiles.
- auto-driver external retries, context retries, blocked execute retries, and execute tier escalation remain outer control loops. They should see a phase only after the internal fallback chain succeeds or exhausts.
- semantic auto retries must not consume fallback models.

## Implementation Plan

1. Add golden characterization tests for current single-string behavior: `AgentMode.__iter__`, `profile_to_phase_models`, persisted resume, execute tier routing, prep routing, local/cloud preflight, and selected-model identity.
2. Add fallback chain helper and tests.
3. Extend profile/tier/prep validation to accept TOML arrays and normalize to chains.
4. Update profile policy rewrites to map across chains.
5. Define the canonical string encoding for persisted `phase_model` and update persisted-state validation/control paths to decode it.
6. Thread chains through tier resolution, prep stage resolution, adaptive critique, and worker fanout without changing `AgentMode.__iter__`.
7. Add the backend-normalized retryability classifier and unit tests for trigger/no-trigger cases.
8. Add ordered attempt execution near `run_step_with_worker` for non-execute phases.
9. Preserve execute fallback chains for validation/preflight/status, but block automatic execute fallback in v1 with an explicit unsafe-execute decision.
10. Extend routing ledger/receipts/status/active-step/history output.
11. Add local/cloud/chain preflight preservation checks.
12. Add docs and update `partnered-5` only after tests prove compatibility.

## Minimum Test Matrix

- string phase spec still validates and dispatches unchanged
- TOML array phase spec validates
- TOML array tier spec validates
- empty array fails validation
- non-string array member fails validation
- policy rewrites apply to every chain element
- explicit `--phase-model` suppresses tier fallback
- primary success does not attempt fallback
- retryable primary failure attempts second spec
- non-retryable primary failure does not attempt second spec
- all specs fail and error includes all attempted specs/reasons
- execute fallback does not run after accepted structured output
- adaptive critique fallback works per complexity tier
- routing ledger records configured/attempted/selected specs
- persisted `phase_model` with encoded fallback chain loads on resume
- override set-model preserves scalar override semantics and suppresses tier fallback
- cloud preflight reports full chain dependencies
- chain milestone parsing does not flatten fallback chains
- prep fanout fallback is per unit
- extreme parallel review does not change topology in v1
- execute fallback is explicitly blocked in v1 even when a chain is configured

## Open Questions

1. Should context exhaustion be fallback-enabled by default? My recommendation: no. Make it opt-in because context failures often indicate prompt or scope problems.
2. Should fallback from Codex to Hermes be allowed for execute? My recommendation: not in v1. In v2, allow it only for provable pre-output infrastructure failures; never for mid-mutation timeouts unless timeout recovery proves no result, evidence audit, merge, checkpoint, or git mutation exists.
3. Should explicit CLI overrides support fallback lists in v1? My recommendation: no. Keep v1 profile-only and add CLI once the internal model is proven.
4. Should fallback preserve the original session key or use the successful model? My recommendation: use a fresh session for fallback attempts and record the successful model; do not reuse a poisoned session across provider families.

## Recommended First Cut

Ship fallback for profile/tier/prep TOML arrays, but limit automatic fallback to non-execute provider/transport failures before accepted output. Preserve all existing single-string behavior. Add observability from day one. Preserve and preflight execute chains, but do not automatically fall back during `execute`/`loop_execute` in v1. Defer richer CLI syntax, context-exhaustion fallback, and execute fallback until there is field evidence and explicit no-output/no-mutation telemetry.
