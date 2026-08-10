# T0.2 off-volume evidence manifest

Captured `critique-ledger-accountability-v2-20260728` at `2026-08-02T14:24:00Z` using `t02-off-volume-collector/1.0`.

The manifest maps bounded, redacted copies into `objects/sha256/`. The remote host was reachable over direct SSH read-only transport. The container exec probe was attempted but failed with `OCI runtime exec failed: ... no space left on device`; host bind-mounted evidence remained readable. No legacy cloud command, mutation, provider query, marker edit, restart, cleanup, or notification was performed.

Claims: **319**; explicit gaps/omissions: **3**; unique content-addressed objects: **230**; unique object bytes: **83611704**.

Run `python3 verify_manifest.py` from this directory to independently re-hash every content-addressed object and validate the logical mappings. The formal T0.2 criterion is recorded as satisfied only when that verifier passes and the gaps remain explicit.
