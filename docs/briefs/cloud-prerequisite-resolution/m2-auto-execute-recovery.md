# M2: Auto And Execute Recovery

## Outcome

Use the structured resolution contract to let auto/execute recover from prerequisite and quality blockers conservatively and repeatably.

## Scope

IN: shared blocker recovery evaluation, quality resolution persistence, execute PhaseResult metadata, terminal override recovery, status/progress suggested commands, and focused tests for unresolved, accepted, fixed, and malformed blockers.

OUT: chain-level cloud status and long-running cloud supervision.

## Locked Decisions

Unresolved, rejected, manual-required, malformed, or unstructured blockers remain terminal. Accepted prerequisite blockers may rerun execute. `accepted_with_debt` quality blockers may advance only with evidence and a debt note. `fixed` quality blockers require rerun/removal before advancing.

## Done Criteria

Auto and override paths use the same evaluator, do not consume quality retry budget for prerequisite recovery, and expose enough blocker detail for an operator or supervisor to recover without editing JSON.
