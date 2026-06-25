# select-tournament

## Purpose

`select-tournament` chooses a winner from a candidate set by composing three
Port-bound stages:

```text
score_candidates (fanout) -> pairwise_bracket -> winner
```

## Runtime

`select-tournament` is a native-first pipeline. Fresh runs through
`megaplan run select-tournament ...` or
`arnold pipelines run select-tournament ...` execute on the native runtime.
Native-born runs resume on native, and corrupt native cursors fail closed
rather than silently falling back to graph.

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
