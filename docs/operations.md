# Operations

## Code Artifact Cache Cleanup

Production should schedule the expired API cache cleanup entry point:

```bash
python scripts/cleanup_code_artifacts.py --store supabase
```

For local SQLite stores, pass the database path:

```bash
python scripts/cleanup_code_artifacts.py --store sqlite --db arnold.db
```

The command deletes expired `code_artifacts` rows where `kind='api_cache'` and
`expires_at` is older than the command's run time. The production scheduler is
an operational choice; the repository only provides the runnable entry point.
