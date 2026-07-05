Working directory: /Users/peteromalley/Documents/Arnold

Read this design doc:
.megaplan/fallback-model-research/model-fallback-design.md

Task: Think through all the places this fallback feature could apply and exactly when it should move down to the next model. Inspect the repository where needed. Treat the main question as trigger/scope policy, not syntax.

Return:
- every phase/path that can dispatch a model and whether fallback should apply there
- exact trigger conditions for moving to the next model
- exact conditions where fallback must not trigger
- special handling for execute, adaptive critique, prep research, review, tiebreakers, cloud/chain, auto-driver retries, and existing runtime fallback
- any telemetry/state needed to diagnose fallback behavior
- unresolved policy decisions that need owner judgment

Keep the answer direct and technical. Do not edit files.
