# jokes Pipeline

Purpose: provide a tiny standalone SDK pipeline that drafts, tightens, and
emits a joke artifact without delegating to the `creative` pipeline.

Runtime: `jokes` is a native-default converted pipeline. Fresh runs through
`megaplan run jokes ...` or `arnold pipelines run jokes ...` persist runtime
ownership in `state.json.runtime_envelope.runtime` and
`state.json.meta.executor`. During the M7 deprecation window, the derived graph
remains available as a compatibility fallback: pass `--runtime graph` (or the
deprecated `--executor graph`) for a fresh run that must use the graph
executor. Existing graph-born plan directories keep resuming on graph.
Native-born runs resume on native, and corrupt native cursors fail closed
rather than silently falling back to graph.

Topology:

```text
draft -> tighten -> emit -> halt
```

Stages:

| Stage | Prompt key | Behavior |
| --- | --- | --- |
| `draft` | `draft_joke` | Dispatches the initial premise and writes the draft artifact. |
| `tighten` | `tighten_joke` | Reads prior artifacts from state and sharpens the joke beat. |
| `emit` | `emit_joke` | Emits the final artifact path into `state["joke_artifact"]`. |

Verdicts: no planning gate vocabulary; each stage returns the next graph edge
label and the final stage returns `halt`.
