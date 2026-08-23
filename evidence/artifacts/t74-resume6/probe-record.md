# T74RESUME6 — remedy D scratch nlink probe record (the Grok probe)

Executed 2026-08-23 ~22:19–22:21 UTC inside container megaplan-cloud-agent-resident-only,
disposable dir /tmp/arnold-t74-resume6-probe/{wrap,baseline}. Design identical to the
ratified T74RESUME5 probe ([tool.uv]-bearing frozen cffi==2.0.0 project mirroring the
candidate's neutralizing condition). Wrapper sha256 641843ee… staged at box
/root/t74-resume6/uv-bin/uv and container /tmp/arnold-t74-resume6-uvwrap/uv (identical
digests); execs staged uv 0.12.5 b65f23a4….

## Executions

- v1 script /root/t74-resume6/probe-nlink.sh (sha256 d7624203cdb567c9e9084850b1282aa97daacb8c2bbebccc5fd420c0c340b849):
  DEFECTIVE EXECUTION, verdict never rendered — a staging-edit defect dropped the two
  census lines and swallowed sync stderr, leaving an undiagnosable baseline sync rc=2.
  No census numbers produced; nothing was concluded; recorded here for honesty.
- v2 script /root/t74-resume6/probe-nlink-v2.sh (sha256 211916f2b656784e9a5f31f0c7b56d33c21d405323c5dfcac1073535c5c364c6):
  the single authoritative probe execution. Verbatim output:

```
== lock (via wrapper) ==
Using CPython 3.13.14
Resolved 3 packages in 7ms
IDENTICAL-BYTES
== baseline venv + sync (NO wrapper) ==
Using CPython 3.11.11 interpreter at: /root/.pyenv/versions/3.11.11/bin/python3.11
Creating virtual environment at: .venv
sync_rc=0
Installed 2 packages in 7ms
 + cffi==2.0.0
 + pycparser==3.0
BASELINE files=63 nlink_gt_1_files=41
.venv/lib/python3.11/site-packages/cffi-2.0.0.dist-info/METADATA
.venv/lib/python3.11/site-packages/cffi-2.0.0.dist-info/licenses/AUTHORS
.venv/lib/python3.11/site-packages/cffi-2.0.0.dist-info/licenses/LICENSE
== wrapped venv + sync (remedy D) ==
Using CPython 3.11.11 interpreter at: /root/.pyenv/versions/3.11.11/bin/python3.11
Creating virtual environment at: .venv
sync_rc=0
Installed 2 packages in 19ms
 + cffi==2.0.0
 + pycparser==3.0
WRAPPED files=63 nlink_gt_1_files=0
```

## Reading

- Sensitivity control (no wrapper): 41 of 63 installed files hardlinked — reproduces the
  resume3/resume4 hardlink condition even with [tool.uv] present.
- Remedy D (wrapper first on PATH): 0 of 63 files with nlink != 1 — UV_LINK_MODE=copy
  forced at spawn defeats the [tool.uv] ancestor-config boundary.
- Flow-env replica resolution check (pre-probe): `command -v uv` →
  /tmp/arnold-t74-resume6-uvwrap/uv; `uv --version` → uv 0.12.5 through the wrapper.

Probe PASSED -> card authorized proceeding to the single S9 attempt
(--supervisor-timeout 2400 per card amendment). Probe dirs left disposable under
/tmp/arnold-t74-resume6-probe (removed post-S9 per disposable-roots discipline).
