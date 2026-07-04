# Boundary Contract Semantic Health

## North Star

Every workflow boundary has one declared durable contract, and every producer,
transition gate, status view, repair loop, watchdog, and auditor reads from that
same contract.

A boundary is complete only when its declared durable effects are present,
coherent, and authorized.

## Why This Exists

The cloud prep incident exposed a process/state gap:

- prep work ran and wrote artifacts;
- `state.json` stayed `current_state=initialized`;
- history lacked prep success;
- `phase_result.json` was missing or stale;
- watchdog/status saw liveness and activity, not semantic progress failure.

The related cloud custody drift class exposed a second gap:

- a process can appear partially alive across watchdog, repair-loop, status, and
  auditor views;
- `active_step` may point at a dead worker PID;
- repair may restore execution as an unmanaged background process;
- status may classify the run as running from process evidence while no layer
  proves expected tmux/supervisor custody.

The immediate root bug was fixed in the prep/state merge path, but the broader
system still lacks a standard way to say:

> This boundary crossed a semantic line, but durable lifecycle evidence did not
> cross with it.

It also lacks a standard way to say:

> This cloud run is alive, but not under the expected custody contract.

This initiative merges three threads into one generalized boundary program:

- structured output / BoundaryTurn stage boundaries;
- TransitionWriter / transition-policy authority gates;
- semantic-health detection, repair triggers, status, and auditor evidence.

## End State

The system has a shared boundary vocabulary that covers Megaplan phases and
future workflow boundaries. It is deliberately split into three concepts:

- `BoundaryContract`: the declared durable effects expected at a boundary;
- `BoundaryReceipt` / `BoundaryEvidence`: what the producer or observer proved
  actually happened;
- `SemanticFinding`: a mismatch between the contract, evidence, authority, and
  current durable reality.

This split prevents `BoundaryContract` from becoming a god abstraction that
executes work, observes work, judges work, and repairs work.

Contracts can declare:

- boundary identity and invocation identity;
- declared inputs;
- scratch outputs;
- canonical outputs;
- receipts;
- `phase_result`;
- expected state delta;
- expected history entry;
- transition decision, where authority increases;
- external effect refs;
- expected custody, for cloud/process boundaries;
- completion and in-progress witnesses;
- staleness policy;
- owner and repair domain.

Boundary producers emit receipts/evidence. Transition writers authorize
state/routing changes. Semantic health compares contracts, receipts, event
journals, warrants, state projections, and current durable reality. Repair,
cloud status, and the 6h auditor consume the same structured findings.

`state.json` is one projection of boundary reality, not the sole arbiter.

## Core Invariants

1. No boundary is considered complete from activity alone.
2. A model-filled template is never canonical until the harness validates and
   promotes it.
3. A canonical artifact without matching state/history/receipt/phase-result
   evidence is a semantic-health finding.
4. A state transition without required artifact/evidence/transition decision is
   a semantic-health finding.
5. Authority-increasing transitions require durable decisions with pinned
   evidence.
6. Child/reducer outputs never advance parent state directly.
7. The repair queue receives structured findings, not prompt-only hints.
8. Watchdog, repair-loop, status, and auditor must not maintain separate
   definitions of progress.
9. A cloud/process boundary is not healthy merely because some matching process
   exists; custody must be one of the explicitly accepted outcomes.
10. Producers write evidence; transition writers mutate lifecycle/routing;
    evaluators produce findings; repair attempts fixes; only evaluators clear
    findings.

## Relationship To Existing Work

This initiative intentionally absorbs and aligns:

- `.megaplan/initiatives/legacy-loose-briefs/notes/structured-output-template-boundaries.md`
- `.megaplan/initiatives/boundary-turn-end-to-end`
- `.megaplan/initiatives/evidence-first-pipeline-semantics/briefs/m7-transition-validator-routing.md`
- cloud superfixer hardening from the prep-state incident.

It should not create a permanent parallel semantic-health registry. Early prep
checks may be bespoke as a bridge, but the long-term source of truth is the
boundary contract.

## Execution Strategy

Start narrow, then generalize:

1. Ship the prep semantic guard first so current cloud runs are protected.
2. Use that guard to prove the contract shape.
3. Introduce the shared contract model.
4. Migrate BoundaryTurn/template promotion and TransitionWriter onto that model.
5. Broaden semantic-health coverage phase by phase.
6. Make repair, status, and auditor consume the same findings.

Do not wait for the whole contract architecture before catching the known prep
failure class. Do not stop after the prep guard and leave a second registry.
