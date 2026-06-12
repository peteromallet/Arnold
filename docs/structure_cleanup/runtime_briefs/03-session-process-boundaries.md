Working directory: /Users/peteromalley/Documents/reigh-workspace/vibecomfy

Task: Audit runtime session/process/server boundaries.

Focus files:
- `session.py`, `server.py`, `server_process.py`, `client.py`, `run.py`,
  `execution.py`, `attempt.py`, `discovery.py`, `fingerprint.py`.

Questions:
- Which files are public runtime boundaries?
- Which are internal process-management helpers that should be private or grouped?
- Are any duplicate wrappers or stale helpers deletable?
- What focused tests would prove the recommendation?

Do not edit files. Output a concise table under 900 words.
