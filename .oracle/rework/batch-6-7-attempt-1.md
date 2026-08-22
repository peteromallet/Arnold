# Combined B6+B7 Rework Triage — Attempt 1

## Finding 1 — ACCEPT (blocking)

**Evidence:** `megaplan/cli/__init__.py` calls `ensure_runtime_layout` before every resident action; `_core/io.py` consequently creates `.megaplan/{plans,initiatives,schemas}` and schema files. This contradicts the attestation fast-path’s prohibition on unrelated pre-admission state. Existing `FileStore` and standalone-attestation constructors already create resident-owned state.

**Criterion / North Star:** R3 / Done criterion 3; **User-owned** and “A generator that generates more than it documents.”

**Required outcome:** Bypass `ensure_runtime_layout(root)` only in top-level resident dispatch. Preserve initialization for cloud, bakeoff, incident, and generic Megaplan commands. Resident actions create only state they own.

**Classification:** [XHARD] → `openrouter:stealth/ox-alpha`; small code seam, custody-sensitive semantics and shared-dispatch regression risk.

**Acceptance / validation:** Fresh resident commands create `.megaplan/resident` as needed, never `plans`, `initiatives`, or `schemas`; a non-resident command still creates the generic layout.

`python -m pytest tests/agentbox/test_cli.py::test_resident_dispatch_creates_only_resident_owned_state tests/agentbox/test_cli.py::test_non_resident_dispatch_still_initializes_generic_layout -q`

## Finding 2 — ACCEPT (blocking)

**Evidence:** Launcher tests use a shell recorder, never production attestation/runtime code. The external-profile dry-run test explicitly forbids attestation and service startup. No test composes all required transitions.

**Criterion / North Star:** Batch 6 checkpoint and R3 / Done criterion 3; **User-owned**.

**Required outcome:** Add one no-network generated-resident integration test using a committed temporary repo. Exercise actual exact-HEAD standalone issuance, external-profile construction, process-attestation creation/validation, and normal Discord startup; mock only process identity and the network service boundary.

**Classification:** normal → `codex:gpt-5.6-luna`; bounded integration-test composition.

**Acceptance / validation:** All four transitions are asserted and exactly one mocked service start occurs.

`python -m pytest tests/agentbox/test_cli.py::test_generated_resident_startup_attests_constructs_profile_creates_process_attestation_and_starts_mock_service -q`

## Finding 3 — ACCEPT (advisory)

**Evidence:** `resident_profile.py.tmpl` embeds generation-time `{{REPO}}`; the env template duplicates profile/store values overridden by launcher flags.

**Criterion / North Star:** Batch 6 T9 and R3 / Done criterion 3; **User-owned**.

**Required outcome:** Derive repository root from `Path(__file__).resolve()`. Keep launcher flags authoritative; remove redundant profile/store env entries and reconcile tests/docs. No loader or custody redesign.

**Classification:** normal → `codex:gpt-5.6-luna`; bounded template repair.

**Acceptance / validation:** A relocated generated tree imports and reads only its relocated agent; redundant env settings are absent.

`python -m pytest tests/agentbox/test_cli.py::test_cli_new_resident_profile_is_relocatable tests/agentbox/test_cli.py::test_cli_new_resident_creates_exactly_five_files -q`

`python -m pytest tests/agentbox/test_cli.py tests/agentbox/test_resident_profile.py tests/cloud/test_standalone_runtime_attestation.py -q`
