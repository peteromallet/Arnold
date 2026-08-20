# Critique Ledger capacity-bootstrap reclaim adversarial review

Reviewed at: `2026-08-02T22:02:29Z`

Disposition: **NO-GO as currently implemented; conditional GO after the bounded fixes below.**

This review is deliberately narrow. It assesses the shortest safe route from the
observed host `free_bytes=0` condition to a fresh zero-recovery canary predeploy
gate, without restarting the historical resident and without deleting the
preserved stopped container, its image, volumes, workspace, deploy directory, or
host cache paths.

## Evidence and inspected state

The authoritative live receipt reports:

- exact stopped container `megaplan-cloud-agent` with ID
  `277d2e6dbc149e01b25881350238a7b0ff5de78cc27d8ef52c144dca7c35c5ab`;
- image ID
  `sha256:de249469ec93ae57eec650b743a08e5a9790dd9612755f2118b6a3ac7149db94`;
- one RW bind from `/opt/megaplan-cloud/workspace` to `/workspace`;
- ext4 `/dev/sda1` mounted at `/` with `free_bytes=0` and
  `free_inodes=33138248`;
- prelaunch `NO-GO`, specifically `prelaunch_free_bytes_below_reserve`;
- historical Docker state error containing `no space left on device`.

Live receipt:
`.megaplan/subagents/critique-ledger-recovery/CLOUD/live-containment-capacity-observation-20260802T214853Z.json`

Receipt SHA-256:
`b1c42795d81d5c8f259ccbc21626fbf6e05c093e18c6c52dcf176d6fb133082b`

The preliminary capacity inventory was explicitly rejected as authoritative
evidence because its workspace scope collection had an off-by-one defect. Its
figures are still useful only as a hypothesis for choosing the least destructive
first action: approximately 3.83 GB of dangling build cache, versus an
approximately 389.9 GB stopped-container writable layer that must not be pruned.
The inventory must be rerun through the corrected parser before any mutation.

The candidate was an actively changing, uncommitted worktree based on
`26aca6ace7f0af3279ca5b311e6983d4904a4d3a`. At the review snapshot its diff
SHA-256 was
`73350c70ae3fec08150afe99cea213a48d6973b65a15064170da79371ef5b00f`.
Inspected file hashes were:

- `ssh_preflight.py`: `76f2037c2328d8cc15bbf44d379e723efc7e65a9804d75824486e4e4dd232d37`
- `ssh.py`: `52989340b22c5400a2dac155f6819757ac64462001aaf66e3fbeac6faac70c9b`
- `zero_recovery.py`: `d8f34dcde0531b835f769e90c02bce643d7dacffcd800cf3394d657174ee38e2`
- `cli.py`: `6d503283900f132bbc1cc9390834ac31ec9927286807d91c1678453ca6b79546`

Because the candidate was changing concurrently, these hashes—not a branch name
alone—identify the code reviewed here.

## What is appropriate

The least destructive first reclaim is exactly:

```text
docker builder prune --force
```

without `--all`/`-a`. This operation is limited to dangling build cache. The
bootstrap surface must make it impossible to select a different command or add
arguments. It must never call `docker system prune`, `docker container prune`,
`docker image prune`, `docker volume prune`, `docker builder prune -a`, `rm`, or
any configured-path deletion. It must not remove or replace the historical
container during capacity bootstrap.

The likely 3.83 GB cache is enough to clear the configured 1 GiB plus 1 MiB
prelaunch byte floor if the preliminary figure is confirmed. It is not proof
that the subsequent image build will fit. The operation must remeasure and stop
at `NO-GO` if the exact post-reclaim floor is not met; the normal predeploy probe
must run again after the build and immediately before deployment.

## Blocking findings in the current implementation

### 1. Stop-then-prune leaves a restart window

The bootstrap script stops units one at a time, attempts persistent masks, and
permits ENOSPC mask failures before pruning. A stopped timer/path can be
reactivated by a still-live trigger or external systemd job; a unit already
queued can run after a superficially inactive observation. If prune fails after
the stops, the script exits with units unmasked and the historical ensure path
can return.

At zero root bytes, use `systemctl mask --runtime --now` for the fixed allowlist
before pruning. Runtime masks are written under `/run`, not the full root
filesystem. Stop/mask activation sources first (all timers and the path), then
their services. Verify every non-absent unit is inactive and runtime-masked, and
verify no queued systemd job targets the allowlist. Only then may prune run.

After bytes are available, install persistent masks while the runtime masks are
still in force. Acceptance must require persistent `UnitFileState=masked`, not
merely `LoadState=masked` or `masked-runtime`. Runtime fencing should remain in
place. On any partial failure, retain every achieved fence and emit/reconcile a
typed failed/ambiguous result; never silently return to an enabled state.

### 2. Container identity lacks a lifecycle epoch

The remote bootstrap compares container ID, image ID/ref, bind, and a derived
`stopped` value. A container can start and stop between observations while
retaining all of those values. That is precisely the event this recovery must
exclude because one short resident start can emit notifications.

Bind and compare at least the raw Docker state status, `StartedAt`, `FinishedAt`,
and `RestartCount` in addition to ID/image/bind. Require the exact supported
stopped state, not merely `Running=false`. Recheck this epoch:

1. before any unit mutation;
2. after runtime masking and before prune;
3. immediately after prune;
4. after persistent masking.

Any change is a hard `NO-GO`, with fences retained.

### 3. Bootstrap evidence is insufficiently cross-bound

`_require_bootstrap_no_go` currently does not establish all of the following:

- the prelaunch observation's embedded container is the exact outer container;
- the prelaunch mount identity is the same filesystem measured by inventory;
- inventory errors are exactly empty;
- inventory scopes are the exact configured workspace/deploy/cache scopes in
  exact order, with no omissions or additions;
- the byte-floor check is false, the inode-floor check is true, and low bytes—not
  an unrelated durability error—are the reason reclaim is authorized;
- prelaunch and inventory free byte/inode values agree at the transaction seam.

These must be checked in both proposal construction and final validation. The
current broad recursive search for any string containing `ENOSPC` is not a
substitute for these typed relationships.

### 4. Historical ENOSPC permanently blocks post-reclaim deploy

The current predeploy gate rejects ENOSPC text anywhere in the outer container
observation. Docker's stopped `.State.Error` is historical and remains present
after host capacity has been reclaimed. Consequently, a fresh capacity probe can
be `GO` while `_require_predeploy_go` still rejects forever.

Record the historical error but do not use its stale text as current capacity
authority. Deployment must require a fresh successful capacity/durability probe,
stable exact stopped container epoch, and exact bind/mount identity. Current
ENOSPC authority comes from the fresh probe, not a historical state message.

### 5. Inventory parsing is not yet authoritative enough

The corrected remote script tightened `du` to exactly two fields and checks the
reported path, which is necessary. The public inventory parser still accepts
arbitrary or empty Docker JSON rows containing string keys/values and therefore
cannot prove the preliminary reclaimable figures. Either validate a supported
exact Docker row schema and normalize sizes to integer bytes, or treat Docker
rows as diagnostic-only and never use them as authority. The fixed prune can be
authorized by typed current low-capacity evidence because the effect is bounded
and safe even if it reclaims zero bytes.

All parsers must reject duplicate JSON keys, extra/missing scopes, reordered
scopes, non-integer/negative capacity, unexpected stderr, multiple JSON values,
wrong mount identity, and malformed/unknown Docker output.

### 6. “Non-replay” cannot be honestly claimed from current storage

An O_EXCL intent under `/run` prevents a duplicate transaction during the same
boot. An O_EXCL receipt in the workspace prevents an ordinary same-ID retry.
Neither is rollback-resistant: `/run` disappears on reboot, and a workspace
receipt can be deleted or rolled back. The provider's in-memory consumed set has
the same limitation across processes.

For this bootstrap, make replay harmless rather than claiming impossible
replay: the only destructive effect remains idempotent, bounded dangling-cache
prune; achieved masks are monotonic and never automatically removed; receipts
are O_EXCL and exact. External monotonic consumed-grant authority belongs in the
follow-up epic. The receipt/schema should say `same_boot_replay_fenced` or
`bounded_idempotent`, not globally `non_replay`, unless such authority exists.

### 7. Failure receipts and time bounds are missing

The fixed remote process can hang on systemctl, Docker, or `du`; subprocesses
have no timeouts. It also raises plain exceptions after partial mutations, so a
caller may receive no typed receipt describing which fences or prune effects
landed.

Use bounded timeouts. A timeout after dispatch is an ambiguous effect, not proof
of no effect. The operation must enter reconciliation: reobserve unit state,
container epoch, and capacity without rerunning a broader mutation. If enough
space exists, persist a typed failure/ambiguous receipt. Never unmask as cleanup.

## Required atomic bootstrap sequence

One fixed allowlisted remote program—not separated client-side commands—should:

1. Strictly validate the expiring proposal, target, exact scopes, command class,
   and fixed argv.
2. Observe and bind the exact stopped container identity, bind, and lifecycle
   epoch; bind prelaunch and inventory mount/capacity evidence.
3. Reserve a same-boot O_EXCL intent under `/run/lock`.
4. Runtime-mask-and-stop all fixed activation sources, then fixed services.
5. Verify runtime masks, inactive states, no queued jobs, no forbidden host
   sessions/processes, and an unchanged stopped container epoch.
6. Execute exactly `docker builder prune --force` once.
7. Reobserve the unchanged stopped container and post-prune filesystem capacity.
8. While runtime masks remain, create persistent masks for every present unit.
9. Verify persistent masks, inactive states, no queued jobs/runtimes, unchanged
   container epoch, exact mount identity, and post-reclaim byte/inode floors.
10. Persist an O_EXCL, fsync'd typed receipt and its directory. Include exact
    argv, return code, proposal/inventory digest, pre/post capacity and mount,
    container pre/after-stop/after-prune/final epoch, unit before/runtime/final
    states, queued jobs, forbidden runtimes, and whether the result is passed,
    failed, or ambiguous.
11. Run a fresh ordinary capacity/durability probe. Do not reuse bootstrap
    inventory as deploy authority.

If the post-reclaim floor is not met, the correct stable result is: historical
container still stopped, units remain fenced, no deploy attempted, and a typed
`NO-GO` receipt. Do not escalate to deleting the 389.9 GB stopped container,
images, volumes, workspace, deploy directory, or caches without a separate
evidence-backed authorization.

## Minimum hostile tests before cloud use

1. Exact successful route: low bytes, exact stopped epoch, dangling prune only,
   post-floor met, runtime then persistent masks, strict receipt.
2. Assert command reachability excludes `-a`/`--all`, system/container/image/
   volume prune, container removal, and filesystem deletion.
3. Runtime-mask failure at zero bytes: no prune and typed `NO-GO`.
4. Timer/path fires or a systemd job is queued during fencing: no prune.
5. Unit absent, already runtime-masked, already persistently masked, active,
   activating, deactivating, failed, or unknown; only exact safe states pass.
6. Prune fails, hangs, SSH disconnects, or frees partially: fences remain;
   reconcile without assuming no effect or blindly replaying.
7. Persistent mask fails after successful prune: runtime masks remain and result
   is non-passed.
8. Container starts, restarts, pauses, removes, is replaced, changes bind, or
   start/finish/restart epoch changes at every seam: hard `NO-GO`.
9. Historical `.State.Error=ENOSPC` plus fresh capacity `GO`: bootstrap history
   is retained but fresh predeploy is allowed if all current checks pass.
10. Fresh capacity below floor, inode floor failure, mount replacement, symlinked
    scope, reordered/missing/extra scope, `du` path mismatch, malformed/duplicate
    JSON, hostile Docker rows, stderr, negative/bool capacity: no mutation.
11. Same transaction replay in-process and same-boot: rejected; reboot/workspace
    rollback limitation is explicitly reported and effect remains bounded.
12. Receipt write/fsync failure after prune: no unmask; reconciliation reports
    ambiguous/failed with observed final state.
13. Verify the historical container ID and all Docker images/volumes survive the
    bootstrap unchanged.
14. Verify a subsequent fresh predeploy transaction is issued only after the
    ordinary durability probe is `GO` and expires/rebinds immediately before its
    first deploy mutation.

## Acceptance decision

The **strategy** is appropriate and is the shortest defensible route: fence the
old recovery authorities, prune only dangling build cache, then rerun fresh
predeploy. The **current implementation is not yet safe enough to touch the
cloud** because it can leave a restart window, cannot detect a fast start-stop,
does not fully bind bootstrap evidence, can permanently reject post-cleanup due
to stale ENOSPC text, and lacks typed partial-failure reconciliation.

Cloud-use acceptance requires the required sequence and hostile tests above,
plus an independent review of the exact resulting commit/tree. Even then, the
claim is bounded recovery safety, not “this can never happen again.” Durable
capacity policy, external monotonic anti-replay, and long-horizon retention/
durability belong in the already-created follow-up epic.

## Custody statement

This was a read-only adversarial review of the candidate and supplied evidence.
I did not contact the cloud host, execute any remote/provider operation, mutate
the candidate worktree, change Git refs, remove data, stop/start a service, or
deploy/relaunch anything. The only write performed was this requested Markdown
review report.
