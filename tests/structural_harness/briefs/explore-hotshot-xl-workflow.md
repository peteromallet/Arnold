# Explore: add Hotshot XL to an SVD-XT workflow

The user wants to add Hotshot XL to an SVD-XT (Stable Video Diffusion XT) workflow.

Run the canonical VibeComfy executor entrypoint,
`vibecomfy.executor.core.run_executor`, for the query
"Hotshot XL SVD-XT workflow". Build an `ExecutorRequest` and freeze the
returned `ExecutorResult` as `evidence/executor_result.json`.

Also freeze `evidence/executor_report.json`, the implementation result as
`evidence/implementation_result.json`, the implementation payload as
`evidence/implementation_payload.json`, and the agent-edit research transcript as
`evidence/messages.jsonl`. Record `actions.jsonl` entries showing the executor
ran and that research ran through agent-edit.

The goal is to prove the same executor path used by the frontend/API performs
research by passing a triage-generated research brief into `handle_agent_edit`.
Structural/fake runs must be deterministic and avoid live model calls, but the
frozen shape should match the live agentic flow.
