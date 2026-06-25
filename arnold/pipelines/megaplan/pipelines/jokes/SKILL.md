# jokes Pipeline

Purpose: provide a tiny standalone SDK pipeline that drafts, tightens, and
emits a joke artifact without delegating to the `creative` pipeline.

Runtime: `jokes` is a native-first pipeline. Fresh runs through
`megaplan run jokes ...` or `arnold pipelines run jokes ...` execute on the
native runtime. Native-born runs resume on native, and corrupt native cursors
fail closed rather than silently falling back to graph.

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
