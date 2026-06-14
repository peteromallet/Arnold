"""M4 T11 — typed subprocess oracle (first ``run()`` consumer).

``oracle.run(cmd)`` is the typed-result subprocess seam used by downstream
oracle/judge code paths.  Returns a small dataclass instead of a raw
:class:`subprocess.CompletedProcess` so callers cannot accidentally swap an
oracle invocation for a generic shell-out — the typed boundary is
load-bearing for the M4 substrate-swap design.

Relationship to :func:`megaplan.orchestration.execution_evidence.validate_execution_evidence`
---------------------------------------------------------------------------------------------
``validate_execution_evidence`` is the attestation / notary path: it inspects
a finalize document and decides whether the work is attested.  It must NOT
branch control flow on its own — it never executes user code and never picks
a next action.  ``oracle.run`` is the actual execution seam; the attestation
path stays read-only.  Keeping these two concerns split means a refactor of
either side cannot silently re-enter the other.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import Mapping, Optional, Sequence, Union


@dataclass(frozen=True)
class OracleResult:
    """Typed result from :func:`run`.

    Fields mirror :class:`subprocess.CompletedProcess` but are immutable and
    typed (``exit: int``, ``stdout: str``, ``stderr: str``) so downstream
    code can pattern-match without a stringly-typed surface area.
    """

    exit: int
    stdout: str
    stderr: str


def run(
    cmd: Union[str, Sequence[str]],
    *,
    cwd: Optional[str] = None,
    env: Optional[Mapping[str, str]] = None,
    timeout: Optional[float] = None,
    input: Optional[str] = None,
) -> OracleResult:
    """Execute *cmd* via :mod:`subprocess` and return a typed result.

    ``cmd`` may be a string (executed via the shell) or a sequence of
    arguments (executed directly).  ``cwd``/``env``/``timeout``/``input``
    forward to :func:`subprocess.run`.  Exit code is captured even when the
    command fails (``check=False``) — the caller decides what to do with a
    non-zero exit.
    """

    use_shell = isinstance(cmd, str)
    completed = subprocess.run(
        cmd,
        shell=use_shell,
        cwd=cwd,
        env=dict(env) if env is not None else None,
        timeout=timeout,
        input=input,
        capture_output=True,
        text=True,
        check=False,
    )
    return OracleResult(
        exit=int(completed.returncode),
        stdout=completed.stdout or "",
        stderr=completed.stderr or "",
    )
