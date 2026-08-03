# Built-image offline structural smoke

This fixture replaces the Codex executable only in a derived, test-only image.
It makes no network or provider call and proves no model/backend identity. Its
sole purpose is to drive the real bounded
`init -> plan -> critique -> gate(ITERATE) -> revise -> critique -> gate(PROCEED) -> finalize`
pipeline, with all seven model dispatches crossing the production UID/GID 65532,
no-new-privileges, zero-capability, resource-limit, rollout-capture, and receipt
sealing paths.

Run the executable harness against a clean accepted checkout:

```sh
./run-offline-structural-smoke.sh \
  <exact-production-image-ref> <clean-repo-root> <receipt-output.json>
```

The harness:

1. Resolves the production image to its exact immutable image ID and builds the
   derived fixture without build networking.
2. Creates synthetic root-owned mode-0600 `/root/.codex/auth.json` and
   `config.toml`. They contain no real credential and the fake never contacts a
   provider; their purpose is to exercise the real phase-local copy boundary.
3. Creates the canary container with the production capability, memory, PID,
   tmpfs, no-port, and single-bind arguments, plus `--network none`.
4. Pre-seeds a clean accepted A/B checkout into the fresh host bind, then runs
   `run_canary.py` with its exact Git and four-manifest admission identities.
5. Requires a passing run receipt, exactly seven terminal dispatch records labelled
   `codex_cli_turn_context`, seven ordinal/iteration-bound privilege receipts,
   exactly two gate attempts and one revise, no surviving UID 65532
   process, and exact host-inspected runtime confinement (no network, restart,
   ports, volumes, or extra mounts; an explicit init reaper; only the admitted rprivate bind and tmpfs;
   exact capabilities, NNP, IPC, PID and memory limits). It emits a typed attempt
   receipt binding both image IDs, the exact container and source identities,
   the normalized runtime summary, and the verifier result.
6. On both success and failure, preserves stdout, stderr, container inspection,
   and any run or privilege receipts in the sibling `<receipt-output>.evidence`
   directory before removing the exact test container. Existing receipt or
   evidence paths are never overwritten.

The live bounded cloud canary—not this fixture—is the authority for actual Codex
CLI turn-context evidence.
