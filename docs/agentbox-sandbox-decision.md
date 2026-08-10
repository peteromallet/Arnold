# AgentBox sandbox decision — trusted container boundary (B5)

Status: FINAL. Recorded 2026-08-10 as part of B5 of `docs/omp-replaces-hermes-todo.md`.

## 1. Decision

**bwrap is not viable on the agentbox.** The Hetzner agentbox deliberately
disables unprivileged user namespaces
(`kernel.unprivileged_userns_clone` / seccomp blocks `unshare(CLONE_NEWUSER)`),
so bubblewrap's namespace-based sandbox fails with
`bwrap: Creating new namespace failed: Permission denied` before any worker
can run. Per the upstream guidance for locked-down containers (Docker/K8s
without user-namespace capabilities), the operator relies on container-level
isolation instead.

**Consequence: bwrap-on-box execution is not required anywhere in this
contract.** No gate checks for a working bubblewrap on the agentbox. The
`MEGAPLAN_TRUSTED_CONTAINER=1` path is the accepted execution mode for the
agentbox and for the cloud Docker image.

## 2. Accepted boundary

The real containment boundary on the agentbox is:

| Boundary | Mechanism |
|---|---|
| Process isolation | Container (Docker/systemd-nspawn-style) plus **process-group ownership and group kill** for every worker child (Python records `pgid`; parent termination kills the whole RPC process group). |
| Filesystem containment | **Relocated in-process path validators** (`arnold_pipelines.megaplan.runtime.sandbox`): `validate_terminal_command`, `validate_write_path`, `validate_v4a_patch`, `get_sandbox_cwd`, `SANDBOX_CWD` — plan/worktree writes and command cwd are validated in-process before dispatch, so a model cannot exec or write outside the plan directory even if its prompt says otherwise. |
| Approval semantics | `--yolo` / `--dangerously-bypass-approvals-and-sandbox` is **approval auto-accept**, not filesystem containment. It never weakens the in-process path validators. |
| Writable roots | Plan directory, `~/.omp`, `/tmp`, `/var/tmp`, `/dev/shm`, and the required Git identity files (`~/.gitconfig`, `.git-credentials`, SSH agent sockets). Everything else is read-only. |
| Network | **Inherited** — the container does not implement per-run network policy; egress is whatever the host grants. Documented, not hidden. |
| Container flag | `MEGAPLAN_TRUSTED_CONTAINER=1` (truthy: `1/true/yes/on`) activates the bypass path; `_trusted_container()` in `workers/_impl.py` is the single reader. |

The managed-agent mount map and the adversarial mount/test matrix from the
earlier plan iterations are retained **as a contingency specification for a
future per-run isolation environment** — they are not an agentbox acceptance
requirement and carry no gate.

## 3. Enforcement points

- `workers/_impl.py::_trusted_container()` — single source of truth for the flag.
- `runtime/sandbox.py` — re-exports the relocated in-process validators
  (vendored into the megaplan runtime in B11, breaking the `arnold.agent`
  import edge).
- omp worker (`workers/omp.py`) — validates route/credential/thinking up front
  and runs each attempt in a fresh stateless RPC child whose process group is
  owned and killed by the parent (RpcClient `stop()` group-kill path).

## 4. Verification

- `tests/sandbox/test_omp_sandbox.py` — trusted-mode evidence, relocated
  validator behavior, path/symlink/command rejection tests, empty-cache
  discovery, exact fork cleanup, byte-identical omp `src/`, allowed diff
  limited to docs/examples/launcher.
- There is **no bwrap-on-box check** anywhere.
