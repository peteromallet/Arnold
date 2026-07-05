# Progress Auditor Stage Metrics

Implement deterministic stage-by-stage metrics in the 6-hour progress auditor so every report can answer how many stalls, retries, repair attempts, meta-repair attempts, and external waits happened by lifecycle stage.

This initiative is scoped to the auditor/reporting surface and focused tests. It should not redesign the whole watchdog or repair system.
