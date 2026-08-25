# Rework tasklist — batch-1 attempt 1 (from GateB1 findings)
1. [normal] detect.py parse_env_file catches only OSError; read_text raises UnicodeDecodeError
   on non-UTF-8 -> scan crashes, violating never-crash criterion. Fix: except (OSError,
   UnicodeDecodeError). Regression test: .env containing byte 0xff must be skipped silently.
2. [normal] catalog.py kimi-code auth_kinds missing "env" despite env_keys=("KIMI_API_KEY",).
   Fix: add "env"; extend parity/auth-kind test.
Acceptance: both fixed, new tests green, full onboarding suite green.
