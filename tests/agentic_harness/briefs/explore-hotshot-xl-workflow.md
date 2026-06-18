# Explore: add Hotshot XL to an SVD-XT workflow

The user wants to add Hotshot XL to an SVD-XT (Stable Video Diffusion XT) workflow.

Run the canonical VibeComfy executor entrypoint,
`vibecomfy.executor.core.run_executor`, for the query
"Hotshot XL SVD-XT workflow". Build an `ExecutorRequest` and freeze the
returned `ExecutorResult` as `evidence/executor_result.json`.

Also freeze `evidence/executor_report.json` and the inner executor
`ResearchResult` as `evidence/research_result.json`. Record `actions.jsonl`
entries showing the executor ran and that research ran through the executor.

The goal is to prove the same executor path used by the frontend/API performs
research and returns sources that mention Hotshot XL. Structural/fake runs must
be deterministic and avoid live model calls.
