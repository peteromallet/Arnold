# Area B — persistence WITHOUT fork changes (Explorer B)
agent.db schema v7 auth_credentials table (sqlite-credential-store.ts L758-777): provider TEXT, credential_type TEXT (oauth|api_key), data JSON, identity_key, disabled_cause, timestamps. Stable + documented.
Cascade (auth-storage.ts L5333-5400): runtime > config(models.yml apiKey) > OAuth > login api_key > env var > stored api_key > fallback resolver.
CLI (v17.4.0 installed):
- omp auth-broker import <file|dir> : NO broker needed -> writes local SqliteAuthCredentialStore directly (L634-650). Flags --dry-run --json --provider= --include-disabled. Accepts CLIProxyAPI-style JSON.
- omp auth-broker login [<provider>] : runs OAuth OR api-key paste flow, interactive picker if unspecified; also logout/list/status/migrate/serve/token.
Test isolation: PI_CODING_AGENT_DIR + PI_CONFIG_DIR (+HOME) override agent dir (dirs.ts DirResolver L240-298). Live db holds 9 creds incl deepseek/openrouter api_keys.
RANKED persistence mechanisms: (1) TS store API n/a from Python; (2) SUBPROCESS omp auth-broker import (safe, local); (3) subprocess omp auth-broker login (interactive, good for TTY flow); (4) direct SQLite INSERT = fragile, bypasses migrations/triggers/CAS -> forbidden.
