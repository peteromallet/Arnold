Working directory: /Users/peteromalley/Documents/reigh-workspace/vibecomfy

Task: Audit runtime drift/watchdog/fingerprint files.

Focus files:
- `drift.py`, `watchdog.py`, `watchdog_runtime.py`, `fingerprint.py`.

Questions:
- Do `watchdog.py` and `watchdog_runtime.py` duplicate each other or serve distinct layers?
- Is drift/fingerprint placement correct?
- Any deleted-root import leftovers from node-pack cleanup?
- Any safe deletion or import consolidation?

Do not edit. Return ranked findings under 800 words.
