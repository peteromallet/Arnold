# select-tournament

## Purpose

`select-tournament` chooses a winner from a candidate set by composing three
Port-bound stages:

```text
score_candidates (fanout) -> pairwise_bracket -> winner
```

## Runtime

`select-tournament` is a native-first pipeline whose ``build_pipeline()``
returns a projected ``Pipeline`` shell with a non-null ``native_program``.
Fresh runs through ``megaplan run select-tournament ...`` or
``arnold pipelines run select-tournament ...`` dispatch through the native
runtime. The projected graph shell exists for structural inspection, port
binding, and downstream composition — it does not represent a separate
execution path.

### Bridge-milestone caveat

During the M6→M7 transition, the graph-projected shell is derived from the
native declaration via ``project_graph`` and remains structurally equivalent
to the native program. Native-born runs resume on native, and corrupt native
cursors fail closed rather than silently degrading. The graph shell is a
reflection, not a fallback — there is no ``--runtime graph`` or
``--executor graph`` toggle on fresh runs.

## Verdict Semantics

| Stage | Semantics |
| --- | --- |
| `score_candidates` | Fans out one scoring step per candidate and joins score artifacts into the `candidate_scores` Port. |
| `pairwise_bracket` | Consumes `candidate_scores`, runs deterministic pairwise elimination, and emits the `bracket_result` Port. |
| `winner` | Consumes `bracket_result` and emits the terminal `winner_result` Port. |

## Port Contract

| Producer | Port | Consumer |
| --- | --- | --- |
| `score_candidates` | `candidate_scores` (`application/x-select-tournament-candidate-scores+json`) | `pairwise_bracket` |
| `pairwise_bracket` | `bracket_result` (`application/x-select-tournament-bracket+json`) | `winner` |
| `winner` | `winner_result` (`application/x-select-tournament-winner+json`) | downstream consumers |

All cross-stage data moves through declared `Port` / `PortRef` bindings.
