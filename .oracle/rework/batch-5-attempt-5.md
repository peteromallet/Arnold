+# Batch 5 rework — attempt 5
+
+## Unsafe idempotent object reuse can advance the pointer
+
+**Disposition:** Accept, blocking. `FileExistsError` reuse currently compares parsed JSON only; a matching seed or receipt with tampered mode can pass reuse, after which `_atomic_write()` advances the pointer before the post-publication loader rejects it.
+
+**Required outcome:** Accept an existing seed or receipt only when it is a regular, non-symlink file with mode exactly `0600` and its digest matches the expected immutable object. Validate both reused objects before any pointer update. Otherwise reject without repair, `chmod`, or mutation.
+
+**Classification/model:** **[XHARD]** — this is transaction-ordering across two immutable custody objects and one atomic mutable pointer, with fail-closed filesystem semantics. Select `openrouter:stealth/ox-alpha`; I agree with the declared routing.
+
+**Acceptance:** For either an existing seed or receipt whose content matches but mode is tampered (for example `0644`), publication rejects; pointer bytes are unchanged and no file or mode is mutated. Valid `0600` idempotent reuse remains unchanged. The named regression `test_standalone_publication_rejects_unsafe_mode_reuse_without_advancing_pointer` and focused/two-file suites are green.
+
+**Exact validation:**
+
+`python -m pytest tests/cloud/test_standalone_runtime_attestation.py::test_standalone_publication_rejects_unsafe_mode_reuse_without_advancing_pointer -q`
+
+`python -m pytest tests/cloud/test_standalone_runtime_attestation.py -q`
+
+`python -m pytest tests/cloud/test_runtime_attestation.py tests/cloud/test_standalone_runtime_attestation.py -q`

tokens used
51,563
Created [batch-5-attempt-5.md](/Users/peteromalley/Documents/arnold-oracle/.oracle/rework/batch-5-attempt-5.md).

Validated against the source and delegated review: 184 words, all requested criteria and exact commands included. Tests were not run; this task only emits triage.

Megaplan fallback was necessary because all supported launchers reject the mandated `config show` command.
