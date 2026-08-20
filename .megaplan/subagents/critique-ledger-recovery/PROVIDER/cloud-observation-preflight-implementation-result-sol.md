# Cloud observation/preflight repair — Sol implementation result

Date: 2026-08-02  
Disposition: **candidate only; not accepted and not deploy authority**

## Exact candidate

- Worktree: `/private/tmp/arnold-critique-recovery-cloud-observation-preflight-20260802`
- Branch: `fix/critique-recovery-cloud-observation-preflight-20260802`
- Frozen base: `6787d6363e8fc0603092913ae877db14f3b9fff8`
- Final commit: `26aca6ace7f0af3279ca5b311e6983d4904a4d3a`
- Final tree: `5503c69c36bbd5a404742139d5c93cddad48edf3`
- Subject: `harden cloud host preflight evidence`
- Base-to-candidate patch SHA-256: `41665957b8c8fdba4df5344d1bb66d1eb3fc41278283a1c765e673908a9c9934`

The initially reported `3513e4937096ad57ef01beed56d4fba17aaf2b17` was superseded by lint-only predecessor `96d368de54876aaaec205290e2640d9daf78f3ea`. Independent review of that predecessor returned FAIL (`cloud-observation-preflight-independent-review-luna.md`, SHA-256 `84384d99578e0992a05ab11996d49cc753e343131c7583f483f232f7a5ddefa9`) for four hostile parsing/transport gaps and an ambiguous stopped-container verdict. Commit `26aca6ace7...` repairs those findings; it is the sole current candidate identity.

## Implemented scope

1. `SshProvider._run()` now records return code plus both redacted stderr and stdout on failure, including stderr-empty/stdout-present failures. Failure messages and process-adapter evidence omit raw argv/remote command bytes and force secret redaction even when ordinary output redaction is disabled.
2. `SshProvider` exposes only two fixed host observations—no arbitrary host-command API:
   - allowlisted `docker inspect` of the configured container, producing typed `running|stopped|paused|restarting|missing|unknown`, exit/OOM/error/image identity, `/workspace` bind source, and collector availability;
   - an allowlisted probe of the configured host workspace after exact bind-source/type/RW validation.
3. The workspace probe reports mount/device identity, free bytes and inodes, enforces configured floors, physically reserves the configured receipt bytes, performs file fsync, SQLite `WAL`/`FULL` commit/integrity/checkpoint, atomic receipt replace plus directory fsync, and removes/fsyncs the isolated probe directory. Unknown output, wrong mount, durability/cleanup failure, or reserve shortfall is typed `NO-GO`.
4. SSH status surfaces observe lifecycle before any exec-backed collector. A non-running lifecycle returns `provider_collector_unavailable`/typed status and does not read the in-container snapshot, chain state, or legacy exec fallback.
5. Remote SSH preflight exposes lifecycle and capacity evidence before imports/dependency probes, skips all `docker exec` probes when lifecycle is not `running`, and fails closed on lifecycle/capacity uncertainty. Local-provider preflight remains outside this SSH-only host gate.
6. Added configurable resource floors with template defaults: 1 GiB free bytes after the 1 MiB receipt reserve, 10,000 free inodes, and a 1 MiB physically allocated receipt reserve.
7. Docker-inspect promotion now requires exact JSON types for lifecycle booleans, nonnegative integer exit status, string error/identity fields, and typed mounts; duplicate fields, malformed values, and contradictory lifecycle flags yield typed `unknown` and cannot enable collection or capacity probing.
8. Container absence is recognized only for remote exit 1 plus one narrowly matched Docker error naming the configured container. SSH return 255 and mixed/banner diagnostics always remain transport `unknown`.
9. Capacity `GO` now requires one duplicate-free JSON object with the exact schema and configured workspace/thresholds; exact typed mount and capacity records; all six required checks exactly true; no errors/stderr; return 0; and capacity values consistent with configured floors plus reserve. Unknown, missing, extra, ill-typed, or contradictory evidence is `unknown`/`NO-GO`.
10. SSH host, user, port, and identity inputs are validated both during spec loading and provider construction. Option-shaped/control/whitespace target values are rejected, ports are exact integers in 1–65535, and SSH/SCP/rsync argv construction terminates transport options before the validated destination.
11. SSH preflight emits separate `host_predeploy_verdict` and `collector_launch_verdict`. An exactly observed stopped container with matching bind and capacity/durability may report host `GO` while collector launch remains `NO-GO`; overall launch preflight still fails and performs no `docker exec` checks.

Deploy/build/down/destroy semantics were not changed.

## Changed files

- `arnold_pipelines/megaplan/cloud/cli.py`
- `arnold_pipelines/megaplan/cloud/providers/ssh.py`
- `arnold_pipelines/megaplan/cloud/providers/ssh_preflight.py`
- `arnold_pipelines/megaplan/cloud/spec.py`
- `arnold_pipelines/megaplan/cloud/templates/cloud.yaml.tmpl`
- `tests/cloud/test_cloud_chain_command.py`
- `tests/cloud/test_ssh_prelaunch_observation.py`
- `tests/cloud/test_ssh_spec.py`

Key file SHA-256 values:

- `cli.py`: `d5f78ebb6633ab0cb6020fb52336fcd6a0efb5440982c154aa7fbcd3999fe1c8`
- `ssh.py`: `e7ef5157572090d88b5c7c230324d77ae19d12191bf97a4f314f4c9e39c2a218`
- `ssh_preflight.py`: `246546e476d9e234881d511f0c7adda6b4dac70426c6e1006ea5ad1b1db113df`
- `spec.py`: `d6b3fcb9450419603e09324790a19c650c6fb7715d866112ec144179775db46b`
- `test_cloud_chain_command.py`: `080eef7b9ad9dd818f12d808e6f3fadc38b3871a686cf8c79a545963a3ea4039`
- `test_ssh_prelaunch_observation.py`: `de5ed19451e2dab73636491977219215be1941083cb0a446264cecb4c38cb886`
- `test_ssh_spec.py`: `b74d10ecdc0aabed34ebc1e6cf74d358885c9dff4260702fe4bb4e1f7088c936`

## Verification evidence

Final-candidate author verification produced **366 passing test observations** in two non-overlapping commands:

1. **193 passed** — hostile/new and directly impacted SSH/status/preflight/process-adapter suite:

   `pytest -q tests/cloud/test_ssh_prelaunch_observation.py tests/cloud/test_ssh_deploy.py tests/cloud/test_status_snapshot_cli.py tests/cloud/test_cloud_status.py tests/cloud/test_cloud_chain_command.py tests/cloud/test_process_adapter_wbc.py`

2. **173 passed, 2 expected policy warnings** — adjacent SSH spec/status/snapshot/scaffold/quickstart regression suite:

   `pytest -q tests/cloud/test_ssh_spec.py tests/cloud/test_cloud_status_custody.py tests/cloud/test_status_retirement.py tests/cloud/test_status_snapshot.py tests/cloud/test_status_snapshot_projection.py tests/arnold_pipelines/megaplan/test_initiative_scaffold.py tests/arnold_pipelines/megaplan/test_cloud_quickstart.py`

Both commands ran against the exact final committed content. Historical predecessor evidence was 302 author passes plus root's independent 130 focused passes; those figures do not substitute for independent review of this repaired candidate.

Additional author checks:

- `python -m ruff check` over all seven changed Python files: PASS.
- `python -m compileall -q` over the four changed production Python modules: PASS.
- `git diff --check`: PASS.
- Fresh `uv build --wheel`: PASS; wheel SHA-256 `a5bb55f7374ed5fb80c51eddb0b21a91af1352fc8562f5b3985a29891527e7e9`.
- Installed-wheel import under `/Users/peteromalley/Documents/Arnold/.venv/bin/python -P` from an isolated `/private/tmp` working directory: PASS; imported `arnold_pipelines.megaplan.cloud.providers.ssh_preflight` from the fresh wheel target.
- Final worktree status: clean.

Hostile coverage includes stdout-only provider failures, forced redaction with global redaction disabled, no raw command in WBC evidence, all lifecycle states, exact-type and contradictory inspect fields, duplicate inspect fields, narrowly typed missing versus rc255/banner/mixed transport unknown, unsafe container/path/SSH-target/identity/port injection, explicit SSH argv option termination, non-allowlisted host operation, wrong bind source, byte/inode/durability/cleanup NO-GO, wrong/missing/duplicate/extra capacity schema fields, mismatched thresholds, ill-typed mount/capacity/check/error values, contradictory GO/process/capacity evidence, real local reserve+fsync+SQLite-WAL+receipt cleanup, explicit dual verdicts, and proof that stopped/paused/missing status/preflight paths make no `docker exec` call.

## Limitations and required next gates

- This is a source candidate, not independent acceptance, owner grant, cloud deploy authority, or evidence that the remote container is currently stopped/running.
- No cloud/provider contact, deploy, restart, push, or remote mutation was performed.
- The capacity probe intentionally makes transient isolated writes under the configured host workspace and cleans them up; it is an observation/durability probe, not a persistent capacity reservation.
- Lifecycle inspect and capacity probe are sequential point-in-time observations, not the full T3.1 owner-locked atomic receipt. The accepted predeploy transaction must rerun/rebind them immediately before deploy and preserve fail-closed race/expiry semantics.
- Host `docker`, `python3`, SQLite WAL support, directory fsync, and either `posix_fallocate` or the physical-write fallback are required. Missing/ambiguous support returns `unknown`/`NO-GO`.
- The workspace mount check deliberately requires one exact RW bind from configured `ssh.workspace_dir` to `/workspace`; symlinked, normalized-different, volume-driver, duplicate, or differently sourced mounts are NO-GO until separately designed and accepted.
- The patch does not implement the privileged production Release-Authority adapter, restart the stopped container, reserve long-lived deploy capacity, or replace the broader T3.1 evidence/vector/owner checks.
