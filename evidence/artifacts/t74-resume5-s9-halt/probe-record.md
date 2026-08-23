# T74RESUME5 — remedy D scratch nlink probe record (the Grok probe)

Executed 2026-08-23 ~21:35–21:40 UTC inside container megaplan-cloud-agent-resident-only,
disposable dir /tmp/arnold-t74-resume5-probe/{wrap,baseline}. Verbatim commands and outputs
from the session transcript; dir removed after the halt (digests below are provenance).

## Setup

pyproject.toml (identical bytes in wrap/ and baseline/):

```toml
[project]
name = "t74-resume5-probe"
version = "0.0.0"
requires-python = ">=3.11"
dependencies = ["cffi==2.0.0"]

[tool.uv]
# comment-only table mirroring astrid-first pyproject.toml:103 —
# the committed [tool.uv] presence that defeated ancestor uv.toml discovery.
```

cffi==2.0.0 pin taken from the candidate's committed uv.lock (same pin family the
generation build installs). Lock generated ONCE in wrap/ via `uv lock` through the
remedy D wrapper, then pyproject.toml+uv.lock copied byte-identical to baseline/.

## Replica resolution check (before probes)

```
$ docker exec CTR env -i PATH=/tmp/arnold-t74-resume5-uvwrap:/tmp/arnold-t74-resume3-uv/bin:<CPATH> \
    LANG=C.UTF-8 PYTHONDONTWRITEBYTECODE=1 sh -c 'command -v uv; uv --version'
/tmp/arnold-t74-resume5-uvwrap/uv
uv 0.12.5 (x86_64-unknown-linux-gnu)
```

## Sync replicating install_sync argv (`uv sync --frozen --no-install-project --active`,
VIRTUAL_ENV set, python3.11 venv), census = `find .venv -type f [! -links 1] | wc -l`:

```
== lock (via wrapper) ==
Using CPython 3.13.14
Resolved 3 packages in 135ms
== baseline sync (NO wrapper) ==
BASELINE files=1543 nlink_gt_1_files=41
BASELINE example-multi: .venv/lib/python3.11/site-packages/cffi-2.0.0.dist-info/METADATA
BASELINE example-multi: .venv/lib/python3.11/site-packages/cffi-2.0.0.dist-info/licenses/AUTHORS
BASELINE example-multi: .venv/lib/python3.11/site-packages/cffi-2.0.0.dist-info/licenses/LICENSE
== wrapper sync (remedy D) ==
WRAPPED files=1543 nlink_gt_1_files=0
```

## Reading

- Sensitivity control (no wrapper): 41 hardlinked files — reproduces the resume3/resume4
  hardlink condition even with [tool.uv] present.
- Remedy D (wrapper first on PATH): 0 files with nlink != 1 across all 1543 installed
  files — UV_LINK_MODE=copy forced at spawn defeats the [tool.uv] ancestor-config boundary.

Probe PASSED -> card authorized proceeding to the single S9 attempt.

## Real-flow attestation (post-attempt, after the S9 halt)

The generation built by the actual supervised canary attempt:

```
GEN 05b40a47e3e6b501327899f3624703a660549e080d7c14d8764b7e6c35d79ebc files=7992 nlink_gt_1=0
```

i.e. remedy D was mechanically effective end-to-end in the real flow (copy mode,
nlink=1 across the entire generation tree that take_snapshot scans). The S9 failure is
independent: fixed supervisor budget exhaustion (see t74-verdict.json s9_failure).
