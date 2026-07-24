# M6: Producer-Side Immediate Verification

> Superseded as an executable milestone by C1-C6. Preserved only as historical
> checklist material; it cannot add a prompt, gate, or policy choice to the
> corrective chain.

## Outcome

After a boundary producer believes it completed, the parent/controller re-reads
durable disk state, verifies the just-finished boundary contract, and enqueues
repair immediately if the contract is inconsistent.

This turns semantic failures into fast repair requests instead of waiting for
watchdog polling.

## Scope

IN:

- Add scoped post-boundary verification from the parent/controller side.
- Evaluate only the just-finished boundary, not whole-plan health.
- Re-read from disk; never trust in-memory state.
- Use atomic-write/read-stability assumptions:
  - ignore temp files;
  - retry transient unreadable JSON once;
  - require mtime stability where needed;
  - suppress findings when in-progress witnesses are fresh.
- Enqueue repair directly with structured finding evidence.
- Avoid `_record_failure()` when it would mutate lifecycle state misleadingly.

OUT:

- Whole-plan scans from hot producer paths.
- Hand-advancing or reconciling state in the verifier.
- Broad repair-loop policy changes.

## Locked Decisions

- Producer-side verification is non-mutating except for evidence/repair request
  writes.
- It must not create a second source of lifecycle truth.
- Dispatch is separately gated from observe.

## Done Criteria

1. Parent/controller post-phase verification catches the prep divergence without
   waiting for watchdog.
2. Findings land in the watched repair queue.
3. A still-consistent phase completion enqueues nothing.
4. Tests cover eventual consistency, active in-progress suppression, repeated
   identical finding dedupe, and disabled dispatch.

## Touchpoints

- `arnold_pipelines/megaplan/auto.py`
- `arnold_pipelines/megaplan/handlers/shared.py`
- semantic-health evaluator
- repair request custody from M2
- producer-side tests
