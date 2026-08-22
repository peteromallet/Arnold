# Batch 2 Rework — Attempt 1

## R2.1 — Atomic no-replace publication

- **Finding:** Accept Finding 1 as blocking. `agentbox/cli.py:647-655` checks `target.exists()` before `os.replace(tmp, target)`; a concurrent creator can therefore be silently overwritten. The existing test covers only an already-present target.
- **Goal / North Star:** Agent Goal R2 and Done Criteria 2 and 4; North Star principles **User-owned** and **Elegance over machinery**.
- **Required outcome / scope:** In `agentbox/cli.py`, replace overwrite-capable publication with atomic no-replace publication. Follow the repository precedent in `arnold_pipelines/megaplan/_core/io.py:394-433`: stage the complete file, publish using `os.link(tmp, target, follow_symlinks=False)`, catch `FileExistsError`, report the existing-target diagnostic, and remove the invocation’s temporary file in `finally`. `agentbox/locks.py:60` independently confirms the repository’s `O_CREAT|O_EXCL` convention. Add focused installer tests only.
- **Dependency/order:** Implement first. Finding 2 is logically independent but shares the installer suite.
- **Classification:** **normal** — localized use of an established primitive with no cross-cutting runtime risk.
- **Selected model:** **Luna normal (`codex:gpt-5.6-luna`)**.
- **Acceptance:** A target created between preflight and publication remains byte-for-byte unchanged; command exits 1 with a clean diagnostic; no `.tmp-*` remains; successful installs remain byte-correct.
- **Exact validation:** Add `test_cli_install_omp_agent_race_does_not_clobber_and_cleans_tmp`; run `python -m pytest tests/agentbox/test_cli.py::test_cli_install_omp_agent_race_does_not_clobber_and_cleans_tmp -q`.

## R2.2 — Refuse block-scalar frontmatter rewrites

- **Finding:** Accept Finding 2 as advisory. `agentbox/cli.py:585-609` replaces only the `description: >` or `description: |` line, leaving its indented continuation lines stale.
- **Goal / North Star:** Agent Goal R2 and Done Criteria 2 and 4; North Star principles **Elegance over machinery**, **One runtime, one seam**, and **User-owned**.
- **Required outcome / scope:** Constrain `_rewrite_agent_frontmatter` to reject block-scalar/non-single-line source values with a concise diagnostic before publication. Preserve ordinary JSON-quoted descriptions—including embedded quotes and escaped newlines—and exact body bytes. Change only `agentbox/cli.py` and focused installer tests.
- **Dependency/order:** Implement after R2.1; validate both before the Batch 2 checkpoint.
- **Classification:** **normal** — bounded input-shape validation.
- **Selected model:** **Luna normal (`codex:gpt-5.6-luna`)**.
- **Acceptance:** `>`/`|` block-scalar overrides exit 1 without creating or modifying a target; supported scalars remain green.
- **Exact validation:** Add `test_cli_install_omp_agent_rejects_block_scalar_description`; run `python -m pytest tests/agentbox/test_cli.py -q && python -m pytest tests/agentbox/test_cli.py tests/agentbox/test_resident_profile.py -q && python -c "import agentbox.cli"`.

**Rejected alternative:** Adding a YAML parser; current templates use single-line scalars, so that machinery is unjustified.
tokens used
51,564
# Batch 2 Rework — Attempt 1

## R2.1 — Atomic no-replace publication

- **Finding:** Accept Finding 1 as blocking. `agentbox/cli.py:647-655` checks `target.exists()` before `os.replace(tmp, target)`; a concurrent creator can therefore be silently overwritten. The existing test covers only an already-present target.
- **Goal / North Star:** Agent Goal R2 and Done Criteria 2 and 4; North Star principles **User-owned** and **Elegance over machinery**.
- **Required outcome / scope:** In `agentbox/cli.py`, replace overwrite-capable publication with atomic no-replace publication. Follow the repository precedent in `arnold_pipelines/megaplan/_core/io.py:394-433`: stage the complete file, publish using `os.link(tmp, target, follow_symlinks=False)`, catch `FileExistsError`, report the existing-target diagnostic, and remove the invocation’s temporary file in `finally`. `agentbox/locks.py:60` independently confirms the repository’s `O_CREAT|O_EXCL` convention. Add focused installer tests only.
- **Dependency/order:** Implement first. Finding 2 is logically independent but shares the installer suite.
- **Classification:** **normal** — localized use of an established primitive with no cross-cutting runtime risk.
- **Selected model:** **Luna normal (`codex:gpt-5.6-luna`)**.
- **Acceptance:** A target created between preflight and publication remains byte-for-byte unchanged; command exits 1 with a clean diagnostic; no `.tmp-*` remains; successful installs remain byte-correct.
- **Exact validation:** Add `test_cli_install_omp_agent_race_does_not_clobber_and_cleans_tmp`; run `python -m pytest tests/agentbox/test_cli.py::test_cli_install_omp_agent_race_does_not_clobber_and_cleans_tmp -q`.

## R2.2 — Refuse block-scalar frontmatter rewrites

- **Finding:** Accept Finding 2 as advisory. `agentbox/cli.py:585-609` replaces only the `description: >` or `description: |` line, leaving its indented continuation lines stale.
- **Goal / North Star:** Agent Goal R2 and Done Criteria 2 and 4; North Star principles **Elegance over machinery**, **One runtime, one seam**, and **User-owned**.
- **Required outcome / scope:** Constrain `_rewrite_agent_frontmatter` to reject block-scalar/non-single-line source values with a concise diagnostic before publication. Preserve ordinary JSON-quoted descriptions—including embedded quotes and escaped newlines—and exact body bytes. Change only `agentbox/cli.py` and focused installer tests.
- **Dependency/order:** Implement after R2.1; validate both before the Batch 2 checkpoint.
- **Classification:** **normal** — bounded input-shape validation.
- **Selected model:** **Luna normal (`codex:gpt-5.6-luna`)**.
- **Acceptance:** `>`/`|` block-scalar overrides exit 1 without creating or modifying a target; supported scalars remain green.
- **Exact validation:** Add `test_cli_install_omp_agent_rejects_block_scalar_description`; run `python -m pytest tests/agentbox/test_cli.py -q && python -m pytest tests/agentbox/test_cli.py tests/agentbox/test_resident_profile.py -q && python -c "import agentbox.cli"`.

**Rejected alternative:** Adding a YAML parser; current templates use single-line scalars, so that machinery is unjustified.
