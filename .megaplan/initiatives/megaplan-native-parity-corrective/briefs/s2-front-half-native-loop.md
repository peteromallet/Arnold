# S2 - Front-Half Native Loop

## Objective

Extract prep, plan, critique, gate, and revise-loop semantics into canonical
source and declared policy. This sprint is intentionally coupled: gate and
revise are one loop, and splitting them is how the previous false pass stayed
plausible.

## Legacy 10-Sprint Source Mapping

- Absorbs `m4-front-half-source-extraction.md`.
- Uses the typed boundary and builder slice from S1.

## Scope

In scope:

- prep clarification gate and suspend/resume;
- plan artifact boundaries;
- critique skip, selection, retry, fanout, merge, and adaptive critique policy;
- gate preflight, normalization, reprompt/downgrade, and debt effect;
- bounded critique/gate/revise loop with typed outcomes;
- severity-as-data plus severity-threshold routing as source/policy visible
  topology;
- quarantine or deletion of replaced front-half component/handler carriers.

Out of scope:

- tiebreaker internals, except the typed interface and call/rejoin shape needed
  by the front-half loop;
- execute, review, and override extraction beyond compatibility required to keep
  the loop running.

## Work Required

- Replace front-half component calls as proof carriers with source-visible
  branch, loop, fanout, gate, and policy constructs.
- Ensure critique lens selection may remain phase-local only if resulting
  fanout cardinality is visible to the workflow.
- Keep gate signal building and payload normalization in handlers only when the
  handlers emit typed outcomes and cannot route.
- Delete or quarantine component route/topology metadata as each row moves.
- Extend dead-delete mutation coverage for every replaced front-half carrier.

## Verifiable Completion Criterion

- A reviewer can follow prep through revise in `.pypeline` and named
  subworkflows without consulting `components.py`.
- Split-outcome scenarios pass:
  - prep blocking questions suspend and resume;
  - unresolved blocking flags reprompt/downgrade;
  - critical cap exhaustion blocks;
  - cosmetic-only cap exhaustion force-proceeds.
- Semantic checker emits row-level evidence for every implemented front-half
  row.
- Component carriers for implemented front-half rows are deleted or fenced so
  they cannot route corrected behavior.

## Do Not Close If

- Gate/revise exit conditions remain hidden in handlers or auto-drive.
- The visible source shows a bare call where the report requires branch, loop,
  fanout, or gate structure.
