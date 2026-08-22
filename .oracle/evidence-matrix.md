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
| Batch 7 checkpoint — wheel/sdist resident-template shipping | `.oracle/evidence/wheel-build.txt`; `.oracle/evidence/sdist-contents.txt`; `tests/agentbox/test_package_smoke.py::test_agentbox_wheel_includes_package_and_installed_entrypoint` | Pass: wheel and sdist ship exactly the five resident-template paths; sdist inspection receipt is recorded. | codex:gpt-5.6-luna |
| Batch 7 checkpoint — clean-installed generation and deployment docs | `.oracle/evidence/package-smoke.txt`; `.oracle/evidence/sdist-contents.txt`; `docs/custom-resident-agents.md` | Pass: clean-installed package generation remains covered by package smoke, and docs describe the name-specific env file as the sole secret/deployment source. | codex:gpt-5.6-luna |

## T11 packaging receipts

- `.oracle/evidence/wheel-build.txt`: Hatch wheel build succeeded and includes `agentbox/templates/resident/*`.
- `.oracle/evidence/package-smoke.txt`: 5 package smoke tests passed, including archive resource assertions and clean-venv installed generation.
- `.oracle/evidence/agentbox-import.txt`: `python -c "import agentbox.cli"` exited 0.
- `.oracle/evidence/sdist-contents.txt`: `python -m build --sdist` succeeded; archive inspection found exactly five resident-template paths.

## Done-criteria coverage (.oracle/agent_goal.md)

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | `agent run arnold` returns agentbox-operator-v1 behavior; body byte-parity test green | Pass | R1 row above; `.oracle/evidence/agent-run-arnold.txt`; parity test in `.oracle/evidence/targeted-resident-tests.txt` |
| 2 | `install-omp-agent --name/--description` renames and re-describes; tests green | Pass | R2 row above |
| 3 | `new-resident` scaffolds five files; generated profile imports and dry-run validates; external profile loading rejects bad profiles | Pass | R3 + Batch 3 rows above; `.oracle/evidence/new-resident-demo2.txt`; `.oracle/evidence/package-smoke.txt` |
| 4 | Targeted suites green (`tests/agentbox/test_cli.py`, `test_resident_profile.py`) | Pass with documented exceptions | Batch 2–4 rows above; 89 passed, six pre-existing attestation-env failures |
| 5 | Evidence matrix maps every criterion to a receipt/evidence path | Pass | This table plus rows above |
| 6 | Final oracle review (Sol) passes; North Star alignment confirmed | Pending | Final review scheduled at end of oracle run, before sync/promotion |

Note (wave1-E sense-check): wheel/sdist artifact completeness re-verified against
`git ls-files agentbox arnold_pipelines/megaplan/skills`; dead legacy
`arnold/pipelines/evidence_pack/*` artifact entries removed from `pyproject.toml`
(the active evidence-pack docs ship via `arnold_pipelines/evidence_pack/`);
planning-skill artifact path corrected to
`arnold_pipelines/megaplan/planning/skills/planning/SKILL.md`. See
`.oracle/findings/wave1-e-report.md`.

## Wave 2 packaging deep pass (2026-08-22)

Re-audit of wheel AND sdist data-file shipping against all tracked non-Python
files (`git ls-files` across `agentbox/`, `arnold/`, `arnold_pipelines/`; 190
files). Model: `openrouter/stealth/ox-alpha`.

| Check | Result | Evidence |
|---|---|---|
| Wheel ships every tracked runtime data file (skills data, evidence_pack, strategy CONTRACT/TEMPLATE, profiles, cloud templates/wrappers, conformance allowlists, native SQL migration, agentbox templates) | Pass — sole omission is `arnold_pipelines/megaplan/skills/babysit/SKILL.md`, deliberate via `[tool.hatch.build.targets.wheel].exclude`; runtime babysit installs read `megaplan/data/babysit_skill.md`, which ships | `.oracle/evidence/wave2-packaging.txt`; regression test `tests/agentbox/test_package_smoke.py::test_wheel_ships_every_tracked_runtime_data_file` |
| Sdist ships every tracked runtime data file | Pass — sole omission is dead legacy `arnold/pipelines/evidence_pack/py.typed` (globally excluded; no runtime importer; stray wheel copy exists only because the broad `"py.typed"` artifact re-include overrides exclusion) | same receipt; regression test `::test_sdist_ships_every_tracked_runtime_data_file` |
| pyproject artifact globs | Unchanged — audit found nothing runtime-needed missing from either artifact | same receipt |

Done-criteria impact: criterion 5 receipts strengthened; criterion 4 now also
covered by `7 passed in 22.32s` for the package smoke suite.
