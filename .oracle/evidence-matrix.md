# T11 evidence matrix

Evidence was collected on `oracle-run` by `codex:gpt-5.6-luna` during T11. No commit was created.

| Criterion | Evidence path(s) | Result | Model |
|---|---|---|---|
| R1 runnable named `arnold` | `.oracle/evidence/agent-list.txt`; `.oracle/evidence/agent-run-arnold.txt`; `tests/agentbox/test_resident_profile.py::test_arnold_agent_prompt_has_raw_byte_parity_with_resident_profile` in `.oracle/evidence/targeted-resident-tests.txt` | Pass: installed agent listed and invocation returned the agentbox-operator-v1 rules; six unrelated runtime tests remain expected attestation-env failures. | codex:gpt-5.6-luna |
| R2 customize name/description | `tests/agentbox/test_cli.py::test_cli_install_omp_agent_name_override_changes_filename_and_frontmatter`; `::test_cli_install_omp_agent_description_override_preserves_name_and_body`; `.oracle/evidence/targeted-resident-tests.txt` | Pass within targeted suite; installer customization tests passed. | codex:gpt-5.6-luna |
| R3 scaffold + deploy | `tests/agentbox/test_cli.py::test_cli_new_resident_creates_exactly_five_files`; `::test_cli_new_resident_profile_imports_and_reads_agent_body`; `.oracle/evidence/new-resident-demo2.txt`; `.oracle/evidence/package-smoke.txt` | Pass: five files generated, profile imported, launcher executable; installed-wheel generation also passed. Deployment remains documented/manual for Discord and systemd. | codex:gpt-5.6-luna |
| Batch 1 checkpoint — prompt parity and named agent | `.oracle/evidence/agent-run-arnold.txt`; parity test named above | Pass. | codex:gpt-5.6-luna |
| Batch 2 checkpoint — constrained installer | `tests/agentbox/test_cli.py` installer tests; `.oracle/evidence/targeted-resident-tests.txt` | Pass for installer behavior; targeted command reports 89 passed and six expected failures. | codex:gpt-5.6-luna |
| Batch 3 checkpoint — external profile seam | `tests/agentbox/test_resident_profile.py::test_external_profile_*`; `.oracle/evidence/targeted-resident-tests.txt` | Pass for built-in/external profile tests; targeted command reports six expected runtime-env failures. | codex:gpt-5.6-luna |
| Batch 4 checkpoint — dry-run/backend behavior | `tests/agentbox/test_resident_profile.py::test_agentbox_profile_cloud_resume_uses_injected_backend`; `::test_generated_agentbox_profile_subclass_retains_exact_v0_tool_catalog`; `.oracle/evidence/targeted-resident-tests.txt` | Pass for backend/profile contract tests; runtime integration subset is blocked only by missing launch seed as recorded. | codex:gpt-5.6-luna |
| Batch 5 checkpoint — standalone custody | `.oracle/evidence/standalone-attestation-tests.txt`; `tests/cloud/test_standalone_runtime_attestation.py::test_resident_attest_json_and_plain_contract_via_adapter`; `::test_resident_attest_wrong_head_returns_admission_exit_code_2` | Pass: 42 tests. | codex:gpt-5.6-luna |
| Batch 6 checkpoint — five-file generator and launcher | `.oracle/evidence/new-resident-demo2.txt`; `.oracle/evidence/package-smoke.txt`; `tests/agentbox/test_cli.py::test_run_resident_*` | Pass for generated artifacts and installed package smoke; launcher integration tests are included in the targeted run, with six pre-existing seed-env failures elsewhere. | codex:gpt-5.6-luna |

## T11 packaging receipts

- `.oracle/evidence/wheel-build.txt`: Hatch wheel build succeeded and includes `agentbox/templates/resident/*`.
- `.oracle/evidence/package-smoke.txt`: 5 package smoke tests passed, including archive resource assertions and clean-venv installed generation.
- `.oracle/evidence/agentbox-import.txt`: `python -c "import agentbox.cli"` exited 0.
