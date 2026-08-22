+# Batch 5 rework — attempt 2
+
+## Direct standalone pointer load omits `status/` custody
+
+**Disposition:** Accept, blocking. `load_standalone_runtime_dispatch_pointer()` requires `seeds/` and reaches `receipts/` only through the referenced receipt, but never requires `status/`; direct loads can therefore succeed with missing or unsafe `status/`.
+
+**Required outcome:** Before reading the pointer, call `_require_standalone_operational_dir(state, name, create=False)` for `seeds`, `receipts`, and `status`. Reject missing, symlinked, non-directory, or non-`0700` operational directories without repair or mutation. Keep fresh publication/process paths and cloud behavior unchanged.
+
+**Classification/model:** **[XHARD]** — this closes a fail-closed custody bypass on a direct load boundary while preserving compatibility across fresh paths. Select `openrouter:stealth/ox-alpha`; I agree with the user-declared rationale.
+
+**Acceptance:** Extend `test_standalone_load_rejects_unsafe_reused_directory_at_0755` to cover `status`; add `test_standalone_load_rejects_missing_status_directory`. Direct pointer loads reject unsafe or missing `status/`; valid direct loads remain successful; fresh directories remain `0700`, objects remain `0600`; the focused and two-file suites are green.
+
+**Exact validation:**
+
+`python -m pytest tests/cloud/test_standalone_runtime_attestation.py::test_standalone_load_rejects_unsafe_reused_directory_at_0755 -q`
+
+`python -m pytest tests/cloud/test_standalone_runtime_attestation.py::test_standalone_load_rejects_missing_status_directory -q`
+
+`python -m pytest tests/cloud/test_runtime_attestation.py tests/cloud/test_standalone_runtime_attestation.py -q`

tokens used
60,464
Created [batch-5-attempt-2.md](/Users/peteromalley/Documents/arnold-oracle/.oracle/rework/batch-5-attempt-2.md). It is 159 words and independently validated against the finding, diff, and existing tests.

No tests were run; the document specifies the required future validation commands. The repository-mandated Megaplan launcher was unavailable because all prescribed launchers lacked the `config` subcommand.
