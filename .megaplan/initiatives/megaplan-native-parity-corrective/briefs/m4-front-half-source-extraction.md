# M4 - Front Half Source Extraction

## Objective

Extract prep, plan, critique, gate, and revise-loop semantics into canonical
source and declared policy.

## Scope

In scope:

- prep clarification gate;
- plan artifact boundaries;
- critique skip, selection, retry, fanout, merge;
- gate preflight, normalization, reprompt/downgrade, debt effect;
- bounded critique/gate/revise loop with typed outcomes.

Out of scope:

- tiebreaker internals;
- execute/review/override extraction beyond interface compatibility needed by
  the front-half loop.

## Verifiable Completion Criterion

- Reviewer can follow the front-half flow in `.pypeline` and named
  subworkflows without consulting `components.py`.
- Component carriers for these rows are deleted or quarantined.
- Split-outcome scenarios pass:
  - prep blocking questions suspend/resume;
  - gate unresolved blocking flags reprompt/downgrade;
  - critical cap exhaustion blocks;
  - cosmetic cap exhaustion force-proceeds.
- The semantic checker emits row-level evidence for each implemented front-half
  row.

