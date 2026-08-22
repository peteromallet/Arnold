+# Batch 5 rework — attempt 3
+
+## Rejected standalone loads mutate custody state
+
+**Disposition:** Accept, blocking. `standalone_runtime_launch_dir()` creates missing parents and chmods the state directory before load/read callers invoke `_require_standalone_operational_dir(..., create=False)`, so rejection can repair or mutate reused state.
+
+**Required outcome:** Add a non-mutating standalone state resolver/validator for every load/read path. It must validate the existing root, state, and operational directories without `mkdir`, `chmod`, or writes. Preserve creation/normalization only for true publication and process-create paths; cloud behavior remains unchanged.
+
+**Classification/model:** **[XHARD]** — this is a fail-closed custody-boundary split spanning direct loads and configured process reads. Select `openrouter:stealth/ox-alpha`; I agree with the user declaration.
+
+**Acceptance:** `test_standalone_load_rejection_does_not_mutate_filesystem` proves rejected loads create no directories and change no modes, including missing parents/state/children and unsafe existing state. Valid loads are unchanged. Publication/process-create still create directories at `0700` and objects at `0600`. Focused and two-file suites are green.
+
+**Exact validation:**
+
+`python -m pytest tests/cloud/test_standalone_runtime_attestation.py::test_standalone_load_rejection_does_not_mutate_filesystem -q`
+
+`python -m pytest tests/cloud/test_standalone_runtime_attestation.py::test_publication_pointer_is_content_addressed_and_rejects_tampering -q`
+
+`python -m pytest tests/cloud/test_runtime_attestation.py tests/cloud/test_standalone_runtime_attestation.py -q`

tokens used
42,667
Created [batch-5-attempt-3.md](/Users/peteromalley/Documents/arnold-oracle/.oracle/rework/batch-5-attempt-3.md).

It is 161 words, includes all requested criteria and exact validation commands, and was independently validated after delegated inspection. No test suites were run; this task only emits the rework triage.
