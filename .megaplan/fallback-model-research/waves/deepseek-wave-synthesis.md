# DeepSeek Wave Synthesis

Date: 2026-07-04
Inputs: six DeepSeek V4 Pro audits in `.megaplan/fallback-model-research/waves/results/`

## Judgment Calls Integrated

I am not accepting every recommendation wholesale. The useful changes are:

- Treat execute fallback as out of scope for v1. The execute path merges task updates, writes `execution_batch_*.json`, rewrites `finalize.json`, runs evidence validation, and can mutate the tree in one tight boundary. V1 should only preserve/validate execute fallback chains and refuse automatic execute fallback with a clear reason. A v2 can add pre-first-byte execute fallback after explicit no-output/no-mutation telemetry exists.
- Keep JSON arrays as JSON arrays in observability records. Encoding is only for unavoidable `phase=string` persistence boundaries such as `state.config.phase_model` and chain `phase_model` entries.
- Add `prep_models` to the same scalar-compatibility inventory as `phase_model` and `tier_models`; it is not optional once prep routing is touched.
- Add provider-family comparison to the retryability classifier. Quota/auth fallback is only valid when the next spec has an independent auth/quota path.
- Add `WorkerUnit.fallback_chain` or an equivalent sidecar, not extra tuple positions on `AgentMode`.
- Cloud preflight must scan every spec in every configured chain for dependencies, credentials, and runtime commands.

## Concrete Missing Surfaces Added

- `_agent_requested_explicitly`
- `_vendor_adjusted_default_spec`
- `apply_profile_expansion` tier stripping when scalar overrides suppress tier routing
- `_canonicalize_tier_models_for_json`
- `_validate_resolved_profile_invariants` / `_validate_named_profile_invariants`
- `_resolve_with_inheritance`
- `resolve_prep_models`
- `state.config.prep_models`
- chain/cloud dependency resolution over all fallback specs

## Implementation Shape

The implementation should land as a compatibility-first migration:

1. Add `model_fallback.py` with `FallbackSpecChain`, normalize, encode/decode, provider-family helper, and classifier shell.
2. Widen profile, tier, and prep validation to accept `str | list[str]`; reject empty arrays and non-string members.
3. Map all policy rewrites over chain elements while preserving scalar output for scalar input.
4. Encode only profile-derived multi-spec `phase_model` entries; decode before every `parse_agent_spec` call at persistence/control/dispatch boundaries.
5. Thread chains through tier, prep, adaptive critique, tiebreaker, and fanout resolution.
6. Add ordered attempts for non-execute worker dispatch and per-unit fanout, with configured chains suppressing ambient runtime fallback.
7. Preserve execute chains for preflight/status but classify execute fallback as unsafe in v1.
8. Add observability list fields beside existing scalar fields.
9. Update cloud/chain preflight to walk every chain element.
10. Only then add a real profile using arrays.

## High-Value Test Gates

- Single-string profile behavior is byte-for-byte/route-for-route unchanged.
- `AgentMode.__iter__` still unpacks to four values.
- TOML arrays validate for phase, tier, and prep model values.
- Encoded `phase_model` chains resume correctly.
- Policy rewrites map over every chain element.
- Retryability classifier covers timeout, stall, first-byte stall, rate limit, 5xx, quota, auth, context overflow, parse/schema failures, and execute unsafe.
- Worker dispatch attempts fallback only on retryable non-execute failures.
- Prep/critique/review fanout fallback is per unit and does not change topology.
- Cloud preflight reports dependencies for all specs in a chain.
