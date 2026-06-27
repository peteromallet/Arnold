# Live Graph Explanation Smoke

You are exercising the VibeComfy live headless agent path, not the ComfyUI
browser panel and not a running ComfyUI server.

Ask the agent to explain the supplied workflow graph. The graph is intentionally
small but complete enough to inspect directly: it loads an SD 1.5 checkpoint,
encodes a positive prompt, and sends the model/prompt inputs into a KSampler.

Expected behavior:

- Treat missing live provider readiness as `blocked_prerequisite`, before any
  executor or model work.
- When readiness is satisfied, classify the request as an inspect/explain graph
  turn.
- Do not ask a clarifying question when the graph is sufficient.
- Respond with a non-empty explanation of the workflow.
- Write live headless artifacts with `flow_kind=live_agentic_headless`,
  `dispatcher=real`, and `model_behavior=agentic`.
- Do not import or depend on browser, aiohttp route registration, or a ComfyUI
  server process.
