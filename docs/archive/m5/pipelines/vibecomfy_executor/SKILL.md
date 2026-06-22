---
name: vibecomfy-executor
description: >
  Arnold pipeline that classifies a user query, optionally researches via
  Hivemind/Banodoco, optionally edits a ComfyUI workflow, and always emits a
  final reply.
---

# vibecomfy-executor

A small decision-graph pipeline for routing user queries through the right
mix of research and action.

## Topology

```
classify → research → implement → reply → halt
```

* **classify** — decides which downstream steps are needed.
* **research** — searches the Hivemind/Banodoco corpus when the plan asks for it.
* **implement** — produces an implementation artifact when the plan asks for it.
  If a workflow `graph` is supplied, this stage runs VibeComfy's agent-edit
  machinery and mutates the workflow.
* **reply** — always runs; synthesizes the final response.

## Execution plan

The classifier outputs a JSON plan with three booleans:

```json
{
  "research": true,
  "implement": true,
  "reply": true
}
```

* `research` — query asks about facts, settings, best practices, comparisons, etc.
* `implement` — query asks to create, edit, fix, build, or change something.
* `reply` — almost always true; the final textual answer.

## CLI usage

```bash
python -m arnold run vibecomfy-executor --inputs query="What are the best Wan settings?"
```

To edit a workflow, pass a `graph` input that points to a ComfyUI UI JSON file
(or an inline JSON object):

```bash
python -m arnold run vibecomfy-executor \
  --inputs 'query=Set the KSampler seed to 12345 and the steps to 30,graph=tests/fixtures/agent_edit/flat.json' \
  --plan-dir /tmp/qo-edit-run
```

The positional `input_file` argument maps to `ctx.inputs["draft"]` if provided;
`--inputs query=...` is the recommended way to pass the user query.

## Profiles

The pipeline ships a default profile in `profiles/default.toml` that maps each
stage to a Hermes-backed DeepSeek subagent:

```toml
[profiles.default]
classify   = "hermes:deepseek:deepseek-v4-flash"
research   = "hermes:deepseek:deepseek-v4-pro"
implement  = "hermes:deepseek:deepseek-v4-pro"
reply      = "hermes:deepseek:deepseek-v4-pro"
```

At runtime the resolved profile is available in `ctx.profile`, and each step
constructs the matching `AIAgent` via the canonical key pool. If no worker can
be resolved, steps fall back to fast heuristics or placeholders so the pipeline
can still be tested without a model backend.

To use a different profile:

```bash
python -m arnold run vibecomfy-executor \
  --profile @vibecomfy-executor:default \
  --inputs query="..."
```

## Hivemind integration

The research step calls the public Banodoco PostgREST endpoint
(`https://ujlwuvkrxlvoswwkerdf.supabase.co/rest/v1`) using the anonymous
publishable key. It searches `unified_feed` distillations first, then falls
back to messages/resources.

## Workflow editing

When `graph` is provided and the plan selects `implement`, the pipeline calls
`vibecomfy.comfy_nodes.agent.edit.handle_agent_edit` using the `implement`
profile model as the batch-REPL client. This is the same edit path VibeComfy
uses today, including the same render/apply/gate/emit stages.

The edited candidate graph is written to `edited_graph.json`, the change report
to `edit_report.json`, and a human summary to `implementation.md`.

## Test fixtures

Three example inputs live in `tests/fixtures/`:

| Fixture | Workflow | Query |
|---------|----------|-------|
| `edit_flat_ksampler.json` | `tests/fixtures/agent_edit/flat.json` | Set KSampler seed to `12345` and steps to `30`. |
| `edit_wan_t2v_size.json` | `ready_templates/sources/official/video/wan_t2v.json` | Make the video `512x512` with `49` frames. |
| `edit_qwen_image_scale.json` | `ready_templates/sources/official/edit/qwen_image_edit.json` | Set `ImageScaleToTotalPixels` megapixels to `2.0` and SaveImage prefix to `qwen-edited`. |

Run a fixture from the VibeComfy repo root with Arnold on `PYTHONPATH`:

```bash
PYTHONPATH=/path/to/arnold python -m arnold run vibecomfy-executor \
  --inputs query="Set the KSampler seed to 12345 and the steps to 30",graph=tests/fixtures/agent_edit/flat.json \
  --plan-dir /tmp/qo-flat-test
```

## Outputs

Each stage writes artifacts under the plan directory:

| Stage      | Artifact(s)                                      |
|------------|--------------------------------------------------|
| classify   | `plan.json`                                      |
| research   | `research_summary.md`, `research_tool_calls.json` |
| implement  | `implementation.md`, `edited_graph.json`¹, `edit_report.json`¹ |
| reply      | `reply.md`                                       |

¹ Only when a `graph` input was provided and the plan selected `implement`.

The final reply text is also returned in the run result at `state.reply`.
