Working directory: /Users/peteromalley/Documents/Arnold

Task: Hunt for artifact/receipt/event consumers that may break if run records, shannon_plan, engine_plan, events.ndjson, cost records, or WorkerResult change.

Focus areas:
- docs/worker-result-consumers.md
- arnold_pipelines/megaplan/receipts/**
- arnold_pipelines/megaplan/observability/**
- arnold_pipelines/megaplan/_core/** fanout/result code
- tests that assert receipts/cost/events/schema behavior

Output:
- Missing contracts/gates the final plan should add.
- Specific file/path evidence.
- Distinguish production consumers vs tests/docs.
- Keep under 900 words.
