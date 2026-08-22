+# Batch 5 rework — attempt 4
+
+## Publication rejection partially mutates custody state
+
+**Disposition:** Accept, blocking. Independently reproduced: with missing `seeds`/`receipts` and an existing unsafe-`0755` `status`, `standalone_dispatch_paths()` creates both missing siblings before rejecting `status`.
+
+**Required outcome:** Use preflight-then-create ordering. First preflight all three operational directories non-mutating (`create=False`); absence must be recorded as eligible for later creation, while every existing symlink, non-directory, unreadable, or non-`0700` entry rejects. Preserve strict missing-directory rejection for load/read callers. Only after all three preflights pass may a second pass create missing entries (`create=True`). Fresh publication behavior remains unchanged.
+
+**Classification/model:** **[XHARD]** — fail-closed custody requires transaction-like validation across multiple paths without weakening strict read semantics. Select `openrouter:stealth/ox-alpha`; I agree with the declared routing.
+
+**Acceptance:** With unsafe-`0755` `status` and missing `seeds`/`receipts`, publication rejects and creates nothing; both siblings remain absent and existing modes remain unchanged. A fresh path still creates all three at `0700`; published objects remain `0600`. Add a regression test asserting zero directories created on rejection. Focused and two-file suites are green.
+
+**Exact validation:**
+
+`python -m pytest tests/cloud/test_standalone_runtime_attestation.py::test_standalone_publication_rejection_does_not_create_missing_siblings -q`
+
+`python -m pytest tests/cloud/test_standalone_runtime_attestation.py::test_publication_pointer_is_content_addressed_and_rejects_tampering -q`
+
+`python -m pytest tests/cloud/test_runtime_attestation.py tests/cloud/test_standalone_runtime_attestation.py -q`

tokens used
39,707
Created [batch-5-attempt-4.md](/Users/peteromalley/Documents/arnold-oracle/.oracle/rework/batch-5-attempt-4.md).

Validated against the source and delegated independent review. The artifact is 185 words and includes the exact acceptance criteria and validation commands. No tests were run; this task only emits the rework triage.
