# Independent review — cloud observation/preflight candidate

Date: 2026-08-02

## Verdict

**FAIL / REVISE. Do not integrate or use as predeploy authority.**

The bounded implementation is substantially safer than base and all authored
regression tests pass, but three hostile-evidence failures and one transport
target injection gap remain. In particular, syntactically valid but
schema-invalid JSON can currently be promoted to authoritative `running`, RW
bind, and capacity `GO`. That violates the requested unknown/malformed
fail-closed boundary.

No cloud, provider, owner, process, source, Git ref, or existing artifact was
mutated during this review. Tests used only local/temp fixtures; this report is
the sole repository write.

## Frozen subject

- Worktree:
  `/private/tmp/arnold-critique-recovery-cloud-observation-preflight-20260802`
- Commit: `96d368de54876aaaec205290e2640d9daf78f3ea`
- Tree: `e2f3633739acaa75ccb9324365a1b8b966fc4f4f`
- Base: `6787d6363e8fc0603092913ae877db14f3b9fff8`
- Author report:
  `.megaplan/subagents/critique-ledger-recovery/PROVIDER/cloud-observation-preflight-implementation-result-sol.md`
- Author report SHA-256:
  `16991cecab09a8d6a69ce1e3c763de0c3f6264a6f2134c5952bfe74368dc190f`
- Candidate patch SHA-256, independently matched to the author report:
  `b547da7a2f4eb6725b47615202fdb886bd815f28b8cbcb2fbb03a415f9921b91`
- Worktree was clean before and after review.

## Blocking findings

### B1 — malformed inspect types become authoritative lifecycle and mount truth

`ssh_preflight.py:145-175` uses Python truth coercion for Docker JSON fields:

- `bool(state.get("Running"))`
- `bool(state.get("Paused"))`
- `bool(state.get("Restarting"))`
- `bool(state.get("OOMKilled"))`
- `bool(mount.get("RW"))`

It also accepts untyped/null container, image, exit-code, error, mount type and
mount source fields. A direct hostile probe supplied:

```json
{"Status":"running","Running":"false","Paused":false,
 "Restarting":false,"OOMKilled":"false","ExitCode":"zero","Error":[]}
```

with `RW:"false"`, null container/image identities and the configured bind
source. The result was `status=available`, `lifecycle=running`,
`collector.status=available`, `workspace_bind.rw=true`, `oom_killed=true`, and
`exit_code="zero"`.

Required repair: validate a strict inspect schema before classification. Every
boolean must be exactly `bool`; exit code exactly a nonnegative integer;
container/image/reference/error and mount fields must have the required string
types and nonempty identity where applicable. Any type mismatch or state-field
contradiction is `unknown`; it must never enable the collector or capacity
probe.

### B2 — malformed capacity JSON is accepted as `GO`

`parse_workspace_prelaunch_result()` at `ssh_preflight.py:392-423` accepts any
JSON object when return code is zero and the two strings `status="go"` and
`verdict="GO"` are present. Both of these were returned unchanged as GO:

```json
{"status":"go","verdict":"GO"}
```

```json
{"schema":"wrong","workspace":"/opt/megaplan-cloud/workspace",
 "status":"go","verdict":"GO","checks":{},"errors":["failed"]}
```

The provider's later workspace-string comparison does not close this: the
second object has the expected workspace and would remain GO.

Required repair: require the exact schema and workspace; exact configured
thresholds; typed mount/device identity; nonnegative integer capacity fields;
an empty errors list; and every required check (`byte_floor`, `inode_floor`,
`reserve_fsync`, `sqlite_wal`, `receipt_atomic_fsync`, `cleanup`) exactly
`true`. Reject unknown/duplicate/ill-typed fields and inconsistent status,
return code, thresholds, capacity, or reserve values as `unknown/NO-GO`.

### B3 — SSH transport failure can be misclassified as known missing container

`classify_container_inspect()` at `ssh_preflight.py:89-108` searches diagnostic
text for “no such container” without first distinguishing SSH transport exit
255. The probe

```text
returncode=255
stderr="ssh transport failed; No such container: decoy"
```

returned `status=available`, `lifecycle=missing`. Transport failure is not
container absence.

Required repair: exit 255 is always transport `unknown`; accept `missing` only
from a narrowly validated Docker-inspect error shape and expected remote exit
class. Add hostile banner/mixed stdout+stderr tests.

### B4 — configured SSH target can inject OpenSSH options

`cloud/spec.py::_string()` accepts an SSH host such as
`-oProxyCommand=touch /tmp/decoy`. `SshProvider._target()` then inserts it into
the argv before the fixed host command without an option terminator or target
validation (`ssh.py:51-60`, `:175-179`). The argv list prevents local shell
word splitting, but it does not prevent OpenSSH itself from interpreting a
leading-dash destination as another option.

Required repair: strictly validate host/user/target syntax and reject leading
dashes, control characters, whitespace and option-shaped targets; use the SSH
option terminator where supported. Test the exact resulting argv without
executing it. This review did not run the hostile target.

## Stopped-container handoff gap

The host-side inspection correctly avoids `docker exec` for a stopped
container, and the capacity probe can separately return GO. However,
`cloud/cli.py:3912-3939` always adds a launch-preflight error when the collector
is unavailable; the committed test explicitly expects return code 1 even when
the stopped container has capacity GO. This is safe for launch but does not
provide a typed, independently consumable distinction between:

- `predeploy_host_verdict=GO` — sufficient only to seek a separately authorized
  replacement; and
- `launch_collector_verdict=NO-GO` — the stopped legacy container cannot serve
  in-container launch/status collection.

Add those separate verdicts and bind lifecycle, container/image/mount identity,
thresholds, probe digest/time/expiry and expected replacement target. Overall
launch preflight must remain NO-GO. The deploy path must consume a fresh
owner-bound predeploy receipt rather than treating this point-in-time JSON as
deploy authority.

## Checks that passed

- Failure diagnostics preserve return code, stderr and stdout; tested
  stdout-only/stderr-only paths redact configured secrets even when ordinary
  redaction is disabled, and WBC evidence omits raw argv/command bytes.
- The new host operations construct only fixed Docker-inspect and capacity
  commands; container/workspace shell metacharacter probes fail.
- Valid Docker output reports lifecycle, bind, image, exit, OOM and error;
  stopped/paused/missing paths tested here never enter Docker exec.
- The real local capacity fixture allocates the reserve, fsyncs it, exercises
  SQLite WAL/FULL/integrity/checkpoint, atomically replaces and directory-fsyncs
  a receipt, then removes and directory-fsyncs the isolated probe directory.
- Wrong bind, capacity shortfall, unparseable output, WAL/fsync/cleanup failure
  remain NO-GO.
- SSH-only branching leaves the local-provider regression suite green.
- A fresh wheel built successfully and its installed
  `arnold_pipelines.megaplan.cloud.providers.ssh_preflight` imported under
  `python -P` from the wheel target, not the source checkout.

## Independent commands and results

```text
PYTHONDONTWRITEBYTECODE=1 /Users/peteromalley/Documents/Arnold/.venv/bin/python \
  -m pytest -q -p no:cacheprovider \
  tests/cloud/test_ssh_prelaunch_observation.py \
  tests/cloud/test_ssh_deploy.py \
  tests/cloud/test_status_snapshot_cli.py \
  tests/cloud/test_cloud_status.py \
  tests/cloud/test_cloud_chain_command.py \
  tests/cloud/test_process_adapter_wbc.py
138 passed in 1.60s
```

```text
PYTHONDONTWRITEBYTECODE=1 /Users/peteromalley/Documents/Arnold/.venv/bin/python \
  -m pytest -q -p no:cacheprovider \
  tests/cloud/test_ssh_spec.py \
  tests/cloud/test_cloud_status_custody.py \
  tests/cloud/test_status_retirement.py \
  tests/cloud/test_status_snapshot.py \
  tests/cloud/test_status_snapshot_projection.py \
  tests/arnold_pipelines/megaplan/test_initiative_scaffold.py \
  tests/arnold_pipelines/megaplan/test_cloud_quickstart.py
164 passed, 2 expected policy warnings in 10.32s
```

```text
/Library/Frameworks/Python.framework/Versions/3.12/bin/ruff check \
  <all six changed Python files>
All checks passed!

python -m compileall -q <four changed production Python files>
exit 0

git diff --check 6787d636... 96d368de...
exit 0
```

```text
uv build --wheel --out-dir /private/tmp/t1-provider-wheel.ytAOjh/dist
Successfully built arnold-0.23.0-py3-none-any.whl
wheel SHA-256:
833ebbd385d11d9dc3081ecd4bfa3cc5eb1193a768b4c123d99ac53349af416c

PYTHONPATH=/private/tmp/t1-provider-wheel.ytAOjh/site \
  /Users/peteromalley/Documents/Arnold/.venv/bin/python -P <installed import probe>
imported:
/private/tmp/t1-provider-wheel.ytAOjh/site/arnold_pipelines/megaplan/cloud/providers/ssh_preflight.py
```

The first no-dependency isolated-venv import attempt predictably stopped at
missing `yaml`; it did not indicate a wheel-content failure. The second probe
used the repository's accepted dependency environment while forcing all Arnold
imports to the fresh wheel target and passed.

## Acceptance path

Repair B1-B4, add the explicit stopped-container dual-verdict contract and
hostile regressions, then rerun the same 302 tests, Ruff, compile/diff gates,
fresh-wheel `python -P` import, and an independent review. Even after source
PASS, this commit remains observation/preflight substrate only: no cloud
mutation is authorized until the separate Release-Authority/T3.1 owner-bound
deploy decision consumes a fresh, expiring host predeploy receipt.
