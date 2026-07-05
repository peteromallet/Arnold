---
type: anchor
anchor_type: north_star
slug: sequential-model-fallbacks
title: 'North Star: Sequential Model Fallbacks'
created_at: '2026-07-04T02:08:44.561159+00:00'
---

# North Star: Sequential Model Fallbacks

## End State

Megaplan profiles can declare ordered fallback model chains using native TOML arrays. The harness tries later specs only for availability or infrastructure failures, records what happened, and preserves existing single-string profile behavior.

## Non-Negotiables

- Existing scalar profile, tier, prep, override, resume, and cloud behavior must remain compatible.
- `AgentMode.__iter__` must continue to unpack as exactly four values.
- Fallback is for availability, not quality repair.
- `execute` and `loop_execute` must not automatically fall back in v1; they may parse, preserve, preflight, and report chains but must raise an explicit unsafe-execute decision if fallback would be needed.
- String-only persistence boundaries must use one canonical compact JSON encoding and shared decode helpers.
- Observability arrays are additive; legacy scalar model/spec fields identify the selected attempt.

## Explicit Non-Goals

- No comma-delimited fallback syntax.
- No CLI fallback-list syntax in v1.
- No fallback on malformed model output, schema failures, test failures, gate/review rejection, blocked results, or semantic failures.
- No topology-changing fallback from parallel review to a single reviewer.
- No v1 execute fallback beyond explicit unsafe blocking.

## Allowed Temporary Bridges

- Profile files can be the only user-facing v1 entry point for fallback chains.
- Chain YAML `phase_model` values may carry encoded fallback strings rather than a new nested YAML schema.
- Execute chains may be accepted and preflighted before dispatch supports safe execute fallback.

## Drift Signals

- The implementation retries because an answer was bad rather than because availability failed.
- Existing scalar profiles serialize differently or route differently.
- Fallback chains are flattened to primary specs in cloud, resume, status, or preflight paths.
- Any code adds positional fields to `AgentMode` or breaks tuple unpacking.
- Execute fallback attempts a second model after possible output, checkpoint, merge, evidence validation, or file mutation.
