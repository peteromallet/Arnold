# Is there a distilled/faster way to run?

The user wants to know if there is a distilled or faster way to run
AnimateDiff-based video generation workflows in ComfyUI.

Run the canonical VibeComfy executor entrypoint,
`vibecomfy.executor.core.run_executor`, for the query
"is there a distilled/faster way to run?". Build an `ExecutorRequest` and
freeze the returned `ExecutorResult` as `evidence/executor_result.json`.

Also freeze `evidence/executor_report.json`, the implementation result as
`evidence/implementation_result.json`, the implementation payload as
`evidence/implementation_payload.json`, and the agent-edit research transcript as
`evidence/messages.jsonl`. Record `actions.jsonl` entries showing the executor
ran and that research ran through agent-edit.

The goal is to prove the research route passes the triage-generated research
brief into `handle_agent_edit`, and that the focused query in `messages.jsonl`
uses domain anchors rather than generic words from the raw sentence.
