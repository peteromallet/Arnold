# Built-image offline structural smoke

This fixture replaces the Codex executable only in a derived, test-only image.
It makes no network or provider call and proves no model/backend identity. Its
sole purpose is to drive the real `init -> plan -> critique -> gate -> finalize`
pipeline, with all four model phases crossing the production UID/GID 65532,
no-new-privileges, zero-capability, resource-limit, rollout-capture, and receipt
sealing paths.

Release procedure:

1. Materialize and build the production image from the canonical `cloud.yaml`.
2. Build this derived image with `--build-arg PRODUCTION_IMAGE=<exact image id>`.
3. Create the canary container with the production capability, memory, PID,
   tmpfs, no-port, and single-bind arguments, plus `--network none`.
4. Copy a clean accepted A/B checkout into the fresh bind, then run
   `run_canary.py` with its exact Git and four-manifest admission identities.
5. Require a passing run receipt, exactly four terminal dispatch records labelled
   `codex_cli_turn_context`, four privilege receipts, no surviving UID 65532
   process, and a stopped container. Retain the image IDs and receipt hashes.

The live bounded cloud canary—not this fixture—is the authority for actual Codex
CLI turn-context evidence.
