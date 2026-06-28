"""Project-directory sandbox for hermes tool calls.

Background
----------
The hermes worker invokes ``AIAgent`` from the vendored agent SDK to run
megaplan phases.  In bakeoff runs each profile gets its own worktree
(``.megaplan-worktrees/<plan>/<profile>/``) and the worktree path is
communicated to the model via a ``Project directory: <abs path>`` line in
the prompt.

The execute prompt also embeds user-authored idea text — and that text can
contain its own ``Project: ...`` line.  When a model resolves the conflict by
trusting the user-authored line (we observed DeepSeek do exactly this), it
prefixes every ``terminal`` call with ``cd <wrong-abs-path> && ...`` and
issues ``write_file`` / ``patch`` calls with absolute paths under the wrong
repo.  The audit catches the resulting empty diff after the fact, but by
then writes have landed in the wrong tree.

This module enforces the boundary at the **tool layer** so that no matter
what the prompt says, the model cannot exec or write outside ``project_dir``.

Three knobs:

1. ``SANDBOX_CWD`` ContextVar is set by ``install_sandbox()`` for the
   duration of the with-block.  Tool wrappers read this at call time.

2. The registered handlers for ``terminal``, ``write_file``, and ``patch``
   are wrapped permanently (installed once, idempotent with lock+markers)
   to validate / coerce paths before dispatch.  Refusal is a hard error
   returned to the model so it can correct itself; we don't silently
   rewrite the call.

3. ``read_file`` and ``search_files`` are intentionally **not** sandboxed —
   the model legitimately needs to read e.g. ``/tmp/phase-6-idea.txt`` and
   the megaplan template files.  Only writes / exec are bounded.
"""

from __future__ import annotations

# Re-export boundary-neutral primitives from the SSoT so that
# SANDBOX_CWD is the same Python object whether imported from here or
# from arnold.runtime.sandbox directly.  This fixes the ContextVar
# identity split (SD2).
from arnold.agent.tools.sandbox import (
    SANDBOX_CWD,
    SANDBOXED_EXEC_TOOLS,
    SANDBOXED_WRITE_TOOLS,
    SandboxViolation,
    get_sandbox_cwd,
    validate_terminal_command,
    validate_v4a_patch,
    validate_write_path,
)

# Re-export wrapper machinery from SSoT (arnold.agent.tools._sandbox_wrappers).
from arnold.agent.tools._sandbox_wrappers import (
    install_sandbox,
    _unwrap_all_for_tests,
    _wrappers_installed,
    _wrappers_lock,
    _wrapped_originals,
    _WRAPPERS,
)
