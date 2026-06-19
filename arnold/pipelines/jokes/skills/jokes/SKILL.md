---
name: jokes
description: "jokes Pipeline"
---

# jokes Pipeline

Purpose: provide a tiny standalone SDK pipeline that declares: "I'm a graph
driver, I need dispatch+emit." It drafts, tightens, and emits a joke artifact
without delegating to the `creative` pipeline.

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
