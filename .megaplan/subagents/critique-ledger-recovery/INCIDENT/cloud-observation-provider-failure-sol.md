# Cloud observation provider failure — read-only diagnosis

Date: 2026-08-02  
Target: `critique-ledger-accountability-v2-20260728` / `cl2-wbc-backed-ledger-20260731-1411`

## Verdict

This is a **container-lifecycle failure before the collector**, not an Arnold status/snapshot compatibility or import failure. The configured container object still exists, but it is not exec-able; **missing is ruled out** because supported `cloud logs --no-follow` successfully ran host-side `docker logs megaplan-cloud-agent` and returned that object's historical log. A removed/nonexistent container cannot satisfy that command. The persistent failure of supported `cloud exec 'stat /workspace'` proves the failure occurs at `docker exec`, before Python, Arnold, the snapshot loader, the chain-state parser, or any import can run.

The strongest supported classification is therefore **present but non-running (operationally stopped)**. The current supported surface cannot distinguish `stopped` from the much less likely `paused`/`restarting` states because it has no host-side `docker inspect` operation. Repeated failure plus logs containing only the two historical successful starts, with no restart-loop starts, is consistent with stopped rather than restarting. This residual state-label uncertainty does not weaken the collector verdict.

Frozen T0.2 evidence is coherent with a later stop: at capture, `container-metadata.txt` recorded `Status=running`, `Running=true`, PID 1487, and the bind `/opt/megaplan-cloud/workspace:/workspace`; `connection-docker-ps.txt` recorded `megaplan-cloud-agent Up 45 hours`. Thus the object was running at T0.2 and became non-exec-able afterward.

## What is actually discarded

A current supported probe:

```text
cloud exec ... 'stat /workspace'
=> provider_failed: Command failed: /usr/bin/ssh ... docker exec megaplan-cloud-agent bash -lc 'stat /workspace'
```

establishes that `SshProvider._run()` received **exactly an empty stderr string (`""`)**. There is no captured Docker stderr that can honestly be quoted. At `cloud/providers/ssh.py:62-64`, the provider consults only `result.stderr`; on empty stderr it synthesizes `Command failed: ...` and raises, discarding any nonzero-command `result.stdout`. The underlying Docker/SSH diagnostic is therefore unavailable through the supported interface and may be in stdout. Claiming the usual Docker text (`container ... is not running`) as exact would be invention.

There is a second diagnostic-loss point: `cloud status --all` catches the first `CliError` while reading the snapshot, prints only its class name (`CliError`), then falls back to `_run_cloud_chains()`, which invokes the same `provider.ssh_exec()`/`docker exec` dependency (`cloud/cli.py:5045-5054,5080-5085`). `cloud status --chain` fails even earlier while `read_remote_file()` executes `cat` through the same container (`cloud/cli.py:5494-5504`; `cloud/providers/ssh.py:171-175`). The final JSON emitter does preserve `CliError.message`; the loss happens before it (`cloud/cli.py:5803-5807`).

## Config/runtime findings

The canonical local `cloud.yaml` selects SSH host `159.69.51.216`, host workspace `/opt/megaplan-cloud/workspace`, and container `megaplan-cloud-agent`. Its current `megaplan.ref`/`src_path` names the older `bc0c600c...` candidate, while frozen remote evidence binds installed runtime/source `c7bcb06a...`. That drift must be pinned during release, but it cannot cause this failure: the `stat /workspace` probe does not import or select either runtime; it fails before entering the container.

`SshProvider.logs()` is host-side `docker logs` (`ssh.py:184-194`), whereas status, file reads, and exec all use `docker exec` (`ssh.py:149-175,196-203`). The observed split is exactly explained by a stopped container object.

## Smallest supported predeploy repair

This requires a **pre-launch provider/preflight code commit**. It is not safely deferred to deployment.

1. Preserve failure evidence in `SshProvider._run()`: on nonzero return, redact and report `stderr` and `stdout` (plus return code), with tests for stderr-empty/stdout-present SSH failures.
2. Add one narrow, read-only host-side provider observation (not arbitrary raw SSH): `docker inspect` the configured container and return typed `running|stopped|paused|restarting|missing|unknown`, exit/OOM/error/image identity, and the `/workspace` bind source. Make status emit this result before attempting any `docker exec` fallback.
3. Add the T3.1 predeploy path a host-side, allowlisted check of the bound workspace source for mount identity, bytes, inodes, quota and fsync/WAL/receipt reserve. If container state is not `running`, all exec/import/collector checks must be typed unavailable rather than retried as legacy exec. Any unknown/shortfall remains NO-GO.

Merely changing the error text is necessary but insufficient: T3.1 requires a current capacity/mount observation before mutation, and every existing remote dependency/preflight probe also enters through `ssh_exec()`.

## Deploy implication

The accepted T1.8 commit `06d41e6b7148db4e5b464131762d63fd697db056` **will not resolve this**. Its root adjudication explicitly accepts only a bounded local Stage-A interface and says it is not cloud deploy authority; the code also fails closed without an injected production adapter. It contains neither this SSH-provider observation nor a production container adapter.

The legacy SSH `deploy()` would `docker rm -f` and `docker run` a new container (`ssh.py:116-147`), so a later exact owner-authorized deploy may incidentally restore exec. But using that mutation as the first diagnostic would bypass the mandatory T3.1 current-capacity/mount and displaced-runtime observation and erase the old container object. Therefore the provider/preflight commit must land and pass first; then the exact accepted composite deploy may proceed under its ordinary owner/fence/receipt gates.

No raw SSH or cloud/source/Git/worktree/owner mutation was used. The only live contacts were supported read-only `cloud exec` and `cloud logs --no-follow` observations.
