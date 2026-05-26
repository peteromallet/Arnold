# Characterization gate — M0

This gate freezes the observable behaviour of several core subsystems so that
later refactors (e.g. the M5b CLI split, store backend changes, pipeline
reworks) can detect regressions before they ship.

---

## Downstream milestone policy

1. **Keep the characterization suite green.**  
   Every PR that touches the CLI, store, chain, evaluation, or planning pipeline
   must run the characterisation tests listed below.  A red characterisation
   test is a regression unless the change is an *intentional, explained*
   behaviour change (see rule 2).

2. **Golden updates require a PR explanation.**  
   CLI parser snapshots, pipeline golden fixtures, and store contract assertions
   may need updating when the team deliberately changes behaviour.  Every golden
   update must be accompanied by a PR comment or commit message that explains
   *what* changed and *why* it is not a regression.  Examples of acceptable
   reasons:

   - A new subcommand or CLI flag was added.
   - A deprecated option was removed.
   - The pipeline state machine gained or lost a state.
   - A store backend intentionally changed error semantics.

   Examples of *unacceptable* reasons (these are regressions):

   - A renamed option that was not part of the intentional change.
   - A silently dropped positional argument.
   - A pipeline step that no longer produces an expected artifact.

3. **Regenerate goldens with `--write-fixture`.**  
   When an intentional golden update is needed, regenerate the fixture by
   running the relevant test with the `--write-fixture` flag:

   ```bash
   # CLI parser snapshot
   python -m pytest tests/characterization/test_cli_parser_snapshot.py \
       -k test_generate_fixture --write-fixture

   # Pipeline golden fixtures
   python -m pytest tests/characterization/test_pipeline_golden.py \
       -k test_generate_fixtures --write-fixture
   ```

   Commit both the changed test code and the regenerated fixture in the same
   PR.

---

## Focused pytest targets added by this milestone

Run the full characterisation module to verify the gate:

```bash
python -m pytest tests/characterization/ -v
```

You can also target individual test classes or files.  The full list of
targets introduced by this milestone:

### Import-surface tests (`tests/characterization/test_import_surface.py`)

| Test | Purpose |
|------|---------|
| `TestStoreImportSurface::test_all_symbols_resolve` | Every `megaplan.store.__all__` symbol resolves |
| `TestWorkersImportSurface::test_all_symbols_resolve` | Every `megaplan.workers.__all__` symbol resolves |
| `TestCliImportSurface::test_surveyed_symbols_resolve` | De-facto public surface for `megaplan.cli` (test-imported symbols) |
| `TestChainImportSurface::test_surveyed_symbols_resolve` | De-facto public surface for `megaplan.chain` (including private helpers used by tests) |
| `TestChainImportSurface::test_remote_exec_guard_callable_or_class` | Remote-exec guard symbols `_capture_sync_state`, `ChainState`, `save_chain_state`, `load_chain_state` have expected types |
| `TestEvaluationImportSurface::test_surveyed_symbols_resolve` | De-facto public surface for `megaplan.orchestration.evaluation` |

### CLI parser snapshot (`tests/characterization/test_cli_parser_snapshot.py`)

| Test | Purpose |
|------|---------|
| `TestCliParserSnapshot::test_snapshot_matches_fixture` | `build_parser()` output matches committed JSON fixture |
| `TestCliParserSnapshot::test_lazy_subcommands_are_passthrough_only` | Cloud/resident/bakeoff are `REMAINDER` passthrough entries (documented limitation) |
| `TestCliParserSnapshot::test_root_parser_has_expected_top_level_options` | Sanity: `--actor`, `--backend`, command subparser |
| `TestCliParserSnapshot::test_at_least_expected_subcommands_exist` | Key subcommands are present in the tree |
| `TestCliParserSnapshot::test_nested_subcommands_present` | Nested trees (e.g. `epic snapshot`, `config profiles list`) exist |
| `TestCliParserSnapshot::test_all_option_strings_are_sorted` | Deterministic JSON output invariant |
| `TestCliParserSnapshot::test_fixture_is_readable_json` | Fixture parses as valid JSON |

### Pipeline golden tests (`tests/characterization/test_pipeline_golden.py`)

| Test | Purpose |
|------|---------|
| `TestPipelineGolden::test_fresh_run_matches_fixture` | Full `init → plan/finalize → execute → review/done` pipeline |
| `TestPipelineGolden::test_resume_after_finalize_matches_fixture` | Halt after `finalize`, reread `state.json`, resume to `done` |

### Store contract tests (shared, run across backends)

| Test | Purpose |
|------|---------|
| `tests/test_file_store.py::test_file_store_contract` | `FileStore` fulfils the shared store contract |
| `tests/test_multi_store.py::test_multi_store_contract` | `MultiStore` (two `FileStore` backends) fulfils the shared contract with `home_backend='db'` routing |
| `tests/test_db_store.py::test_db_store_contract` | `DBStore` fulfils the shared contract (skipped unless `--backend db` + `SUPABASE_DB_URL`) |

---

## Quick smoke test

To confirm the gate is healthy after any change:

```bash
python -m pytest tests/characterization/ -v
```

Expected: all active tests pass (2 fixture-generation tests skip without
`--write-fixture`).  If any test fails, determine whether the change was
intentional (see rule 2 above) or a regression that must be fixed before
merge.
