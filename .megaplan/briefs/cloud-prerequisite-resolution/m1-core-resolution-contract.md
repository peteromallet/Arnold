# M1: Core Resolution Contract

## Outcome

Create a structured, persistent contract for resolving cloud prerequisite blocks so later automation can distinguish accepted, waived, satisfied, rejected, and manual-only outcomes without parsing worker prose.

## Scope

IN: state persistence for user-action resolution events, deterministic resolution lookup, CLI support for recording resolutions, prompt/status visibility, and focused tests.

OUT: cloud supervisor loops, chain policy semantics, provider integrations, and slot-first watchdog behavior.

## Done Criteria

Resolution events survive state saves, expose actionable status, and can be consumed by execute/review flows without requiring human review gates.
