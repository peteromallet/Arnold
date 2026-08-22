+# Combined B6+B7 Rework Triage — Attempt 5
+
+## F1 — ACCEPT, blocking: launch is not bound to the admitted project
+
+**Evidence:** `_resident_discord(root, …)` calls `_require_discord_runtime_launch()` without `root`; that helper calls `require_configured_runtime_launch("resident", create=True)` and discards its seed. The validator derives pointer/status custody solely from `seed["project_root"]`. Therefore a valid project-B seed can authorize project-A profile/store/service startup under direct, systemd, or manual invocation; only the generated launcher masks this.
+
+**Criterion + principle:** Batch 5/T8 and Batch 6/T10 exact-root, fail-closed startup; R3 / Done criterion 3. **User-owned** binds bot identity to the launched repo; **Compatibility is a contract** preserves cloud/chain behavior.
+
+**Outcome + scope:** Thread resolved `root` through `_resident_discord` → `_require_discord_runtime_launch` → standalone launch validation. For standalone authority, reject `seed["project_root"] != root` with `runtime_launch_attestation_mismatch` before process-status mutation or profile/runner/service construction. Leave listener recovery and cloud authority unchanged.
+
+**Classification/model:** **[XHARD] → `openrouter:stealth/ox-alpha`**. Agreed: this is an authority/custody boundary with ordering and cloud-regression risk.
+
+**Acceptance/validation:** Add `test_generated_resident_startup_rejects_cross_project_seed_before_profile_or_service_start`: B seed + A launch fails typed, writes no process receipt, and leaves profile/runner/service counters at zero. Matching A seed still starts once.
+
+`python -m pytest tests/agentbox/test_resident_profile.py::test_generated_resident_startup_rejects_cross_project_seed_before_profile_or_service_start tests/agentbox/test_resident_profile.py::test_generated_resident_startup_attests_distinct_roots_constructs_profile_creates_process_attestation_and_starts_mock_service tests/agentbox/test_resident_profile.py::test_generated_resident_two_root_attest_rejects_stale_or_swapped_roots -q`
+
+## F2 — ACCEPT, advisory: unsafe pointer is silently repaired
+
+**Evidence:** Publication rejects only pointer symlinks; `_atomic_write()` replaces an existing permissive regular pointer with a new `0600` file. Seed/receipt reuse instead rejects unsafe custody.
+
+**Criterion + principle:** Batch 5/T8 root-custodied, fail-closed publication and “failure never advances the pointer”; **Compatibility is a contract**.
+
+**Outcome + scope:** Immediately before pointer replacement, `lstat` any existing pointer and require regular, non-symlink, exact `0600`; otherwise reject without changing bytes or mode. Missing pointers remain creatable. Keep this standalone-specific; do not alter shared `_atomic_write()` semantics.
+
+**Classification/model:** **normal → GPT-5.6 Luna**. Agreed: narrow local preflight, not an authority redesign.
+
+**Acceptance/validation:** Add `test_standalone_publication_rejects_unsafe_existing_pointer_without_replacing`; retain valid `0600` replacement and existing seed/receipt reuse coverage.
+
+`python -m pytest tests/cloud/test_standalone_runtime_attestation.py::test_standalone_publication_rejects_unsafe_existing_pointer_without_replacing tests/cloud/test_standalone_runtime_attestation.py::test_standalone_publication_rejects_unsafe_mode_reuse_without_advancing_pointer -q`

tokens used
70,068
Created [batch-6-7-attempt-5.md](/Users/peteromalley/Documents/arnold-oracle/.oracle/rework/batch-6-7-attempt-5.md).

- 302 words
- F1 accepted as blocking, `[XHARD] → openrouter:stealth/ox-alpha`
- F2 accepted as advisory, `normal → GPT-5.6 Luna`
- Baseline validation: 3 targeted tests passed
- `git diff --check` passed
