# jokes Pipeline

Purpose: provide a tiny standalone native-first pipeline that declares:
"I'm a native driver, I need dispatch+emit." The native declaration compiles
a ``NativeProgram`` through ``@pipeline`` / ``@phase`` decorators and
``compile_pipeline``, and ``build_pipeline()`` returns a projected
``Pipeline`` shell whose ``native_program`` field is non-null. It drafts,
tightens, and emits a joke artifact without delegating to the ``creative``
pipeline.

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

Verdicts: no planning gate vocabulary; each stage returns the next native
phase label and the final stage returns ``halt``.

## Native Dispatch

The ``native_program`` attached to the projected ``Pipeline`` is an
execution-level dispatch substrate — it describes the phase ordering, entry
point, and instruction set consumed by the native runtime. It does **not**
encode final visible compositional semantics (those are deferred to the
Megaplan composition layer). The graph-projected shell is a structural
reflection of the native program and exists for inspection, port binding,
and compatibility; the native program is the authoritative execution
contract.
