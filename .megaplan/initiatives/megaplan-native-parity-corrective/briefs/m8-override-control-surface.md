# M8 - Override Control Surface

## Objective

Extract routing override actions into native source while leaving config-only
effects as audited effects.

## Scope

Routing overrides must be source-visible:

- abort;
- force proceed;
- replan;
- resume/recover paths;
- terminal halt behavior.

Config/effect-only overrides may remain effects if they cannot route:

- set model/profile/vendor/robustness;
- add note;
- other non-routing state annotations.

## Verifiable Completion Criterion

- Override routing branches are visible in source with typed outcomes.
- Authority requirements are declared at human/control gates.
- Scenarios pass:
  - force-proceed from blocked reaches finalization/done;
  - abort mid-loop reaches terminal aborted;
  - recover/resume routes do not depend on handler-private action dispatch.
- `LEGACY_ALIASES` into handler-private routing functions are deleted or
  quarantined for implemented rows.

