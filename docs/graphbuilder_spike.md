# GraphBuilder Spike

Decision: enable as an optional backend.

HiddenSwitch includes `comfy_execution.graph_utils.GraphBuilder`. It creates backend-shaped workflow dictionaries with:

```python
from comfy_execution.graph_utils import GraphBuilder

builder = GraphBuilder(prefix="")
image = builder.node("EmptyImage", id="1", width=64, height=64, batch_size=1, color=0)
builder.node("SaveImage", id="2", images=image.out(0), filename_prefix="example")
api_workflow = builder.finalize()
```

VibeComfy implements `VibeWorkflow.compile("graphbuilder")` by building the same graph through `GraphBuilder` and compares it against the direct API compiler in tests.

GraphBuilder should stay optional because direct API-dict compilation is simpler, more transparent, and easier to debug. It is useful for parity with HiddenSwitch internals and for future generated-code work.
