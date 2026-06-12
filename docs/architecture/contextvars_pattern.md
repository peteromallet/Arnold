# ContextVar Workflow Binding

v2.6 ready templates use a context manager to bind the active workflow:

```python
def build():
    with new_workflow(READY_METADATA, source_path=__file__) as wf:
        positive = CLIPTextEncode(text=PUBLIC_INPUTS["prompt"], clip=clip)
        return wf.finalize(PUBLIC_INPUTS, output_node="9", output_type="SaveImage")
```

Generated wrappers call `_current_workflow_or_raise()` when no explicit workflow
argument is provided. The current workflow is stored in a Python
`contextvars.ContextVar`, not `threading.local()`.

Why `ContextVar`:

- it propagates correctly across `asyncio` task boundaries;
- it avoids accidental global state shared between concurrent builds;
- it is the standard Python primitive for scoped dynamic context;
- it keeps the template call site focused on graph semantics, not plumbing.

This mirrors mature Python APIs such as `decimal.localcontext()`,
`warnings.catch_warnings()`, PyMC's model context pattern, and other scoped
builder APIs.

Nesting is intentionally rejected. A ready template should build one workflow;
if an inner `with new_workflow(...)` starts while another workflow context is
active, VibeComfy raises a `RuntimeError` explaining that nested workflow
contexts are unsupported.

If a generated wrapper is called without either an active context or an explicit
workflow argument, VibeComfy raises a clear `RuntimeError` telling the caller to
wrap the build in:

```python
with new_workflow(READY_METADATA, source_path=__file__) as wf:
    ...
```

External callers may still pass the workflow explicitly:

```python
wf = new_workflow(READY_METADATA, source_path=__file__)
positive = CLIPTextEncode(wf, text="hello", clip=clip)
```

That form is supported for compatibility, but generated ready templates should
use the context-bound zero-positional form.
