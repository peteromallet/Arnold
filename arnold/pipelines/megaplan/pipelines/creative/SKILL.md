# creative pipeline — skill reference

**Runtime**: native-default converted pipeline<br>
**Arnold API version**: `1.0`<br>
**Run surface**: `megaplan run creative ...` or `arnold pipelines run creative ...`<br>
**Supported modes**: form-controlled with `--form`

Fresh `creative` runs use the native runtime by default and persist runtime
ownership in `state.json.runtime_envelope.runtime` and
`state.json.meta.executor`. During the M7 deprecation window, the derived graph
remains available as a compatibility fallback: pass `--runtime graph` (or the
deprecated `--executor graph`) for a fresh run that must use the graph executor.
Existing graph-born plan directories keep resuming on graph. Native-born runs
resume on native, and corrupt native cursors fail closed rather than silently
falling back to graph.

## Purpose

Form-aware creative-writing pipeline. Accepts a `--form` (validated against
`megaplan.forms.available_form_ids()`) and an optional `--primary-criterion`,
then produces a finished creative artifact via a single prep→execute→critique
→revise→finalize pass.

## Topology

```
prep (form-aware) → execute_creative → critique_creative → revise_creative → finalize
```

* **prep** — form-aware prep; threads `form` and `primary_criterion` into
  stage state.
* **execute_creative** — primary creative generation stage.
* **critique_creative** — evaluates the draft against the form's criteria and
  `primary_criterion`.
* **revise_creative** — applies critique feedback to produce the final draft.
* **finalize** — wraps and emits the finished artifact; returns `next='halt'`.

## Verdict semantics

The `creative` pipeline is **single-pass** — there is no gate loop. Routing
is strictly linear:

| Label | Meaning |
|-------|---------|
| `execute_creative` | prep done → begin creative generation |
| `critique_creative` | generation done → critique |
| `revise_creative` | critique done → revise |
| `finalize` | revise done → finalize |
| *(halt)* | finalize done → pipeline done |

## Robustness levels

The `creative` pipeline does not implement robustness levels. Depth is
fixed (single pass per stage).

## Forms

The `--form` flag selects a registered form from `megaplan/forms/`.<br>
Default form: `joke`.<br>
Available forms are returned by `megaplan.forms.available_form_ids()`.

Form-specific prompt keys follow the pattern `<key>:joke` for the joke form;
non-joke forms use the generic creative keys with the form id passed through
stage params.

## Prompt keys

| Key | Stage |
|-----|-------|
| `prep` | prep |
| `execute_creative` | execute_creative |
| `critique_creative` | critique_creative |
| `revise_creative` | revise_creative |
| *(none)* | finalize |

Prompt files live under `megaplan/pipelines/creative/prompts/`.
