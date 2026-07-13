# M7: Phase Coverage And Reducer Boundaries

> Superseded as an executable milestone by C1-C6. A "documented exemption" here
> may only be a time-bounded C1-C5 migration exception; C6 permits none for a
> declared supported producer.

## Outcome

Boundary contracts and semantic-health checks cover core Megaplan phases and
reducer/child boundaries.

The system can detect artifact/state/promotion divergence across plan, critique,
gate, execute, finalize, review, tiebreaker, and reducer flows.

## Scope

IN:

- Add contracts for:
  - plan;
  - revise;
  - critique;
  - critique evaluator;
  - gate;
  - execute;
  - finalize;
  - review;
  - tiebreaker;
  - feedback where present.
- Represent reducer semantics:
  - child outputs;
  - aggregate canonical output;
  - parent-state promotion point;
  - side-effect evidence;
  - blocked/retry records.
- Distinguish repair domains:
  - phase writer;
  - artifact promotion;
  - reducer;
  - transition writer;
  - auditor only.

OUT:

- Chain/PR/cloud boundaries.
- Public workflow conformance enforcement.

## Locked Decisions

- Child turns never advance parent state.
- Reducer promotion owns parent canonical artifacts and parent state effects.
- Execute cannot be atomic; it records side-effect evidence and resume anchors.

## Done Criteria

1. Every covered phase has a contract; temporary migration exceptions identify
   an owner and removal milestone and cannot survive final acceptance.
2. Semantic-health tests cover at least one broken contract per phase family.
3. Reducer tests cover child output without reducer promotion and reducer
   promotion without required child evidence.
4. Existing phase behavior and canonical artifact paths are preserved.

## Touchpoints

- plan/revise/gate/finalize handlers
- execute/review/tiebreaker orchestration
- BoundaryTurn reducer code
- semantic-health evaluator
- existing phase and reducer tests
