# doc pipeline — skill reference

**Runtime**: native-default converted pipeline<br>
**Arnold API version**: `1.0`<br>
**Run surface**: `megaplan run doc ...` or `arnold pipelines run doc ...`<br>
**Supported modes**: *(none)*

Fresh `doc` runs use the native runtime by default and persist runtime
ownership in `state.json.runtime_envelope.runtime` and
`state.json.meta.executor`. During the M7 deprecation window, the derived graph
remains available as a compatibility fallback: pass `--runtime graph` (or the
deprecated `--executor graph`) for a fresh run that must use the graph executor.
Existing graph-born plan directories keep resuming on graph. Native-born runs
resume on native, and corrupt native cursors fail closed rather than silently
falling back to graph.

## Purpose

Linear document-production pipeline. Takes a topic and produces a structured
multi-section document via outline-then-draft-then-refine.

## Topology

```
outline → section_drafts (dynamic fanout) → critique → revise → assembly
```

* **outline** — emits a `sections` JSON artifact (list of section specs).
* **section_drafts** — `dynamic_fanout` SubloopStep: fans out one execute
  sub-turn per section, joins via `concat_sections_join`.
* **critique** — single-pass critique step (no gate loop).
* **revise** — single-pass revise step (no gate loop).
* **assembly** — concatenates all section outputs into the final document;
  returns `next='halt'` directly (no outgoing edge needed).

## Verdict semantics

The `doc` pipeline is **single-pass** — there is no `gate` stage and no
iterate/proceed split. The only routing decisions are:

| Label | Meaning |
|-------|---------|
| `section_drafts` | outline passes → begin per-section fanout |
| `critique` | section drafts complete → critique the full draft |
| `revise` | critique complete → apply revisions |
| `assembly` | revise complete → assemble final document |
| *(halt)* | assembly complete → pipeline done |

## Robustness levels

The `doc` pipeline does not implement robustness levels. Depth is
controlled by the number of sections in the outline artifact.

## Prompt keys

| Key | Stage |
|-----|-------|
| `outline_doc` | outline |
| `execute_doc` | per-section draft (inside fanout) |
| `critique_doc` | critique |
| `revise_doc` | revise |
| `assemble_doc` | assembly |

Prompt files live under `megaplan/pipelines/doc/prompts/`.
