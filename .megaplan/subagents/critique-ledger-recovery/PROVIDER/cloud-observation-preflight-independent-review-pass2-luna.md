# Independent review pass 2 — cloud observation/preflight candidate

Date: 2026-08-02

## Verdict

**PASS for bounded source integration as host observation/preflight substrate.**

This is not cloud-deploy authority, a Release-Authority receipt, a capacity
reservation, or evidence of the current remote host/container state. No cloud or
provider was contacted. Cloud mutation remains forbidden until a separately
accepted, fresh, owner-bound predeploy transaction consumes and binds this
substrate's evidence.

## Frozen subject

- Worktree:
  `/private/tmp/arnold-critique-recovery-cloud-observation-preflight-20260802`
- Base: `6787d6363e8fc0603092913ae877db14f3b9fff8`
- Commit: `26aca6ace7f0af3279ca5b311e6983d4904a4d3a`
- Tree: `5503c69c36bbd5a404742139d5c93cddad48edf3`
- Base-to-candidate patch SHA-256:
  `41665957b8c8fdba4df5344d1bb66d1eb3fc41278283a1c765e673908a9c9934`
- Lineage: the stated base is an ancestor; the candidate is two commits ahead
  (`96d368de54876aaaec205290e2640d9daf78f3ea`, then `26aca6ace...`).
- The worktree was clean before and after review.

Prior FAIL report:
`.megaplan/subagents/critique-ledger-recovery/PROVIDER/cloud-observation-preflight-independent-review-luna.md`,
SHA-256 `84384d99578e0992a05ab11996d49cc753e343131c7583f483f232f7a5ddefa9`.

Current author report:
`.megaplan/subagents/critique-ledger-recovery/PROVIDER/cloud-observation-preflight-implementation-result-sol.md`,
SHA-256 `6454319248b199f084f837d152e2ebba8652c0de4f13c5e84d4a5b19e8544ded`.

## Prior blockers re-audited

### Inspect schema and lifecycle — PASS

`classify_container_inspect()` now requires exact booleans for `Running`,
`Paused`, `Restarting`, `OOMKilled`, a nonnegative exact integer `ExitCode`, a
string `Error`, nonempty string container/image identities, a list of typed
mounts, and exact-boolean mount `RW`. Contradictory lifecycle flags classify as
`unknown`; none enable the collector or capacity probe.

Independent mutations replaced every lifecycle boolean with strings, integers,
nulls, lists and objects; replaced exit/error/status and mount fields with
wrong types; and confirmed every case remained `unknown`.

### Capacity JSON and GO promotion — PASS

The parser accepts only one duplicate-free JSON object. `GO` additionally
requires the exact schema, configured workspace and thresholds, exact allowed
top-level fields, typed mount/device identity, nonnegative integer capacity,
all six required checks exactly true, an empty errors list, empty stderr,
return code zero, and capacity consistent with floors plus reserve.

Wrong/missing schemas, unknown fields, missing fields, wrong workspace or
thresholds, nested and top-level duplicate keys, booleans masquerading as
integers, malformed checks/mount/capacity/errors, nonempty errors, insufficient
reported capacity and process-evidence contradictions all return
`unknown/NO-GO`.

### Exit 255 and mixed diagnostics — PASS

Container absence is recognized only for return code 1 and exactly one narrowly
matched Docker diagnostic naming the configured container. Exit 255 always
remains transport `unknown`, including a decoy `No such container` string.
Mixed stdout/stderr or banner text cannot be promoted to known absence.

### SSH/SCP/rsync option injection — PASS for the configured attack surface

Host and user values reject leading dashes, whitespace/control bytes and
embedded `user@host`; ports are exact integers in `1..65535`; identity paths
reject leading dashes and control bytes. Validation runs both while loading the
spec and when constructing `SshProvider`, so direct dataclass construction does
not bypass it.

The independently captured argv shapes were:

```text
ssh -p 2222 -i '/keys/deploy key' -- deploy@example.invalid <command>
scp -r -P 2222 -i '/keys/deploy key' -- /private/tmp/safe-deploy/. deploy@example.invalid:/opt/megaplan-cloud/deploy
rsync -az -e "ssh -p 2222 -i '/keys/deploy key' --" /private/tmp/safe-deploy/ deploy@example.invalid:/opt/megaplan-cloud/deploy/
```

Thus SSH terminates its options before the validated destination, SCP
terminates options before its operands, and rsync's remote-shell command
terminates SSH options before rsync appends the validated destination. The
rsync source is an internally generated absolute cloud-cache path, not a
configured SSH field. If `_sync_deploy_dir()` is ever widened to caller-chosen
relative paths, add an outer rsync operand terminator as defense in depth.

### Dual stopped-container verdict — PASS, bounded semantics

SSH preflight now exposes both:

- `host_predeploy_verdict`: host bind plus capacity/durability readiness; and
- `collector_launch_verdict`: availability of the running in-container
  collector.

An exactly observed stopped configured container with a matching RW bind and a
strict capacity `GO` can therefore report host `GO` and collector `NO-GO`.
Overall preflight still returns failure, records the unavailable collector and
does not invoke `docker exec`. Running plus strict capacity evidence yields both
verdicts `GO`; unknown/malformed lifecycle or capacity remains fail-closed.

These observations are sequential and point-in-time. The later privileged
predeploy owner must rerun them, compare the outer container observation with
the capacity observation's embedded container/image/mount identity, bind the
expected replacement target and exact thresholds, and issue a fresh expiring
receipt. No current code consumes `host_predeploy_verdict` as deploy authority,
so that required later atomicity/expiry layer does not block this bounded source
integration.

## Independent verification

```text
pytest -q -p no:cacheprovider
  tests/cloud/test_ssh_prelaunch_observation.py
  tests/cloud/test_ssh_spec.py
  tests/cloud/test_cloud_chain_command.py
180 passed in 1.32s
```

```text
pytest -q -p no:cacheprovider
  tests/cloud/test_ssh_prelaunch_observation.py
  tests/cloud/test_ssh_deploy.py
  tests/cloud/test_status_snapshot_cli.py
  tests/cloud/test_cloud_status.py
  tests/cloud/test_cloud_chain_command.py
  tests/cloud/test_process_adapter_wbc.py
193 passed in 1.69s
```

```text
pytest -q -p no:cacheprovider
  tests/cloud/test_ssh_spec.py
  tests/cloud/test_cloud_status_custody.py
  tests/cloud/test_status_retirement.py
  tests/cloud/test_status_snapshot.py
  tests/cloud/test_status_snapshot_projection.py
  tests/arnold_pipelines/megaplan/test_initiative_scaffold.py
  tests/arnold_pipelines/megaplan/test_cloud_quickstart.py
173 passed, 2 expected policy warnings in 7.07s
```

The two full commands are non-overlapping: **366 passed** total.

Additional checks:

- Ruff over the seven changed Python files: PASS.
- Compile of the four changed production modules: PASS.
- `git diff --check` from the exact base to candidate: PASS.
- Independent inline hostile probes for inspect type mutations, nested duplicate
  capacity keys, rc-255 decoys, and exact SSH/SCP/rsync argv: PASS.

## Acceptance boundary

Commit `26aca6ace7f0af3279ca5b311e6983d4904a4d3a` is eligible for clean integration
as the bounded host observation/preflight implementation. Acceptance does not
authorize deploy, replacement, restart, container removal, cloud contact, or a
claim that capacity/lifecycle is presently known. Before cloud mutation, the
integrated installed generation still needs independent installed-path parity
and the fresh privileged Release-Authority/predeploy receipt described above.

No cloud, provider, Git ref, tracked candidate file, or existing evidence file
was mutated by this review. This report is the sole intended repository artifact.
