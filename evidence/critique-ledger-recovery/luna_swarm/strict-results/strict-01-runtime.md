Observed runtime identity gap:

- `cloud resume` first runs remote `arnold status`, then executes `cd <workspace> && arnold resume --plan <plan>`.
- On the target container, `arnold` resolves to `/root/.pyenv/shims/arnold`, whose entry point is `arnold.cli:main`.
- That CLI explicitly contains the legacy interface and does not expose the Megaplan command surface; it requires `--artifact-root`.
- The actual chain uses the pinned Megaplan runtime via `python -P -m arnold_pipelines.megaplan ...`, with the intended runtime/source path supplied separately.
- Therefore status/resume use an unpinned legacy console script, while chain execution uses the pinned Megaplan module. The failure occurs before dispatch and is an invocation-lineage mismatch, not a VJ8 or provider failure.

Patch boundary:

Change only the cloud remote Megaplan command adapter: centralize the canonical pinned-runtime/module invocation and use it for both SSH status and resume. Preserve the existing workspace, plan arguments, quoting, and typed recovery behavior. Do not alter ledger semantics, VJ8 expectations, blocker state, lease policy, or recovery transitions in this patch.

Acceptance tests:

1. `SshProvider.status_payload()` emits a remote command invoking the canonical Megaplan module/runtime, never bare `arnold status`, while preserving `--plan`.

2. `cloud resume --plan <plan>` emits the same canonical runtime identity for the resume command and never invokes bare `arnold resume`.

3. A mocked SSH integration test captures both status and resume commands and verifies identical runtime lineage, correct workspace `cd`, exact plan propagation, and shell-safe quoting.

4. A container-level smoke test runs the generated status/resume commands against the pinned runtime and verifies there is no legacy `--artifact-root` error, no fallback to `/root/.pyenv/shims/arnold`, and the typed plan state remains unchanged until the canonical command begins.
