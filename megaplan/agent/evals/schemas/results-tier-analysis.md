# `result.json` Tier Analysis

Analysis date: 2026-03-26

Inputs used:
- All 21 current `EVAL.ts` files from `/Users/peteromalley/Documents/next-evals-oss/evals`
- 889 historical `result.json` files from `/Users/peteromalley/Documents/next-evals-oss/results`

## Gate Verdict

Gate result: proceed

Why:
- `0 / 21` current `EVAL.ts` files reference `__agent_eval__/results.json`, `result.json`, `o11y`, `filesModified`, `filesRead`, `shellCommands`, `toolCalls`, `webFetches`, or related observability fields.
- Tier 3 dependency rate across the current eval assertions is therefore `0%`.
- The current eval suite is overwhelmingly source-tree and file-content based, so scoring does not need a Vercel-only observability dependency to stay viable.

Implication:
- The scoring approach can proceed.
- `result.json` still needs to be generated for compatibility with the existing `@vercel/agent-eval` result shape and for future-proofing, but it is not on the critical path for the current hidden assertions.

## Tier Classification

### Tier 1: Git diff derivable

These can be computed directly from the prepared workspace and the captured initial commit SHA.

| Field | Notes |
| --- | --- |
| `o11y.filesModified` | Best derived from `git diff --name-only <initial_commit_sha>` after execution. |

### Tier 2: Hermes trace or orchestrator derivable

These can be built from Hermes session logs, tool traces, shell execution records, and orchestrator metadata.

| Field | Source |
| --- | --- |
| `status` | Orchestrator verdict (`passed` / `failed`) |
| `duration` | Wall-clock runtime |
| `model` | Configured experiment model label |
| `error` | Orchestrator/runtime failure string |
| `transcriptPath` | Audit artifact path |
| `transcriptRawPath` | Audit artifact path |
| `outputPaths.eval` | Eval output artifact path |
| `outputPaths.scripts.build` | Build output artifact path |
| `o11y.errors` | Trace/tool/runtime errors |
| `o11y.filesRead` | File-read tool invocations or trace-derived file access |
| `o11y.shellCommands` | Terminal tool invocations |
| `o11y.thinkingBlocks` | Assistant reasoning block count from normalized messages |
| `o11y.toolCalls.*` | Tool invocation counts after mapping Hermes tool names to framework buckets |
| `o11y.totalToolCalls` | Sum of mapped tool calls |
| `o11y.totalTurns` | Message/turn count from normalized transcript |
| `o11y.webFetches` | Web tool traces if present |

### Tier 3: Vercel framework only / stub candidates

Current finding:
- No current `EVAL.ts` assertions depend on Tier 3-only fields.
- No extra Tier 3-only keys were required to describe the sampled `result.json` corpus.

Practical interpretation:
- For this snapshot, Tier 3 is effectively empty.
- If future evals begin asserting framework-specific observability that Hermes cannot reconstruct, those new fields should be stubbed explicitly and the gate should be revisited.

## Sampled `result.json` Shape

Observed root keys across 889 sampled results:
- Always present: `status`, `duration`, `model`
- Present on successful/fully-observed runs: `o11y`, `outputPaths`, `transcriptPath`, `transcriptRawPath`
- Present on infra-style failures: `error`

Observed `o11y.toolCalls` buckets:
- `agent_task`
- `file_edit`
- `file_read`
- `file_write`
- `glob`
- `grep`
- `list_dir`
- `shell`
- `unknown`
- `web_fetch`
- `web_search`

Observed `shellCommands` item shape:
- Required: `command`
- Optional: `success`, `exitCode`

## Mismatch With Plan Assumption

The batch plan assumed current `EVAL.ts` files consume `__agent_eval__/results.json`.

Current snapshot finding:
- They do not.
- The real compatibility target is the framework-shaped `result.json` corpus already stored under `next-evals-oss/results/`.

This is favorable for the Hermes integration: the scoring gate passes, and `result.json` generation can stay lightweight and trace-backed rather than Vercel-runtime dependent.
