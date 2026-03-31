# Model Validation Notes

Validation date: 2026-03-26

## Environment
- Hermes repo: `/Users/peteromalley/Documents/hermes-agent`
- OpenRouter credentials file present at `~/.hermes/.env`
- Live OpenRouter requests are blocked in this sandbox: direct calls to `https://openrouter.ai/api/v1` fail with `APIConnectionError: Connection error.`

## MiniMax M2.7 on OpenRouter
Model: `minimax/minimax-m2.7`

Local payload validation:
- Hermes routes this model through `chat_completions`, not `anthropic_messages`.
- Hermes now emits OpenAI-style `response_format` JSON schema payloads for chat-completions models.
- Hermes does not attach OpenRouter `reasoning` extra_body for MiniMax on OpenRouter, which matches the current capability gating in [run_agent.py](/Users/peteromalley/Documents/hermes-agent/run_agent.py).

Live check attempted:
- Request type: `chat.completions.create(...)` with strict JSON-schema `response_format`
- Result: `APIConnectionError: Connection error.`
- Verdict: Structured-output wiring is locally correct, but live OpenRouter behavior remains unverified in this sandbox.

## GLM-5 on OpenRouter
Model: `z-ai/glm-5`

Local payload validation:
- Hermes routes this model through `chat_completions`.
- Hermes emits standard OpenAI tool schemas for file tools.
- `enabled_toolsets=['file']` produces `read_file`, `write_file`, `patch`, `search_files`.
- `enabled_toolsets=['file-readonly']` produces the narrower `read_file`, `search_files` surface intended for planning/critique phases.

Live check attempted:
- Request type: `chat.completions.create(...)` with `read_file` tool schema
- Result: `APIConnectionError: Connection error.`
- Verdict: Tool-call request formatting is locally correct, but live tool-call reliability is unverified here.

## Observed Quirks
- `npm run sync-evals` uses `tsx`, which tries to open an IPC pipe and hits `EPERM` in this sandbox. Running the sync script as `node --import tsx/esm scripts/sync-evals.ts` bypasses that local IPC issue.
- Live OpenRouter calls fail before model-specific behavior can be observed, so there is no trustworthy success-rate number for GLM-5 tool calling in this environment.

## Practical Fallbacks
- If GLM-5 shows malformed or missing tool calls once live testing is available, keep Hermes+MiniMax for plan/revise/gate/finalize and fall back to Claude or GPT-5-family execution models for `execute` and `review`.
- Add a retry/repair wrapper around malformed tool arguments before marking GLM-5 unusable; many failures in this class are formatting failures, not reasoning failures.
- Keep `file-readonly` on non-execute phases and reserve `terminal` plus full `file` access for the execute phase only.
