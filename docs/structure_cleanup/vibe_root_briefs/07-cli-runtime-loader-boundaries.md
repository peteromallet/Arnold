Working directory: /Users/peteromalley/Documents/reigh-workspace/vibecomfy

Task: Audit root modules related to CLI, loading, runtime, and Comfy backend boundaries.

Context:
- There are packages named `commands/`, `runtime/`, `loader/`, and root files like `cli.py`, `cli_loader.py`, `comfy_backend.py`, `comfy_command.py`, `local_library.py`, `scratchpad_loader.py`.
- We need root files to earn their level.
- Do not edit files.

Focus:
- Which are console/public boundaries that should remain root?
- Which are implementation details that belong under packages?
- Which are stale after command/package splits?
- What tests would prove a move/delete is safe?

Output:
- Decision table with exact action, evidence, and tests.
- Keep under 900 words.
