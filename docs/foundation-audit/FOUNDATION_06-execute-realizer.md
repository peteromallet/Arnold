First read `FOUNDATION_PREAMBLE.md` (shared context + output rules). Obey it.

## YOUR SUBSYSTEM: the `execute/` subsystem (future "realizer" substrate) + PR #43 entanglement

Body 3 splits `execute/` into an engine DAG-runner + pluggable `Realizer`s along the `is_prose_mode`
seam. The brief admits `core.py` is ~1770 LOC and there's an OPEN draft PR #43 (98 files,
+11420/-793, branch `worktree-execute-redesign`) that rewrites this surface and is "blocked on
execute-contract reconciliation." Characterize the foundation here.

Investigate (cite path:line):
- `execute/core.py`, `execute/quality.py`, `handlers/execute.py`, `handlers/finalize.py`. The
  `is_prose_mode` branches (~core.py:575-658), `assemble_doc` (execute.py:179), the two
  `required_fields` tuples in `_merge_batch_results`, quality gate git-evidence (quality.py:369-429),
  finalize verification-task injection (finalize.py:295,475).
- Is the code/prose mode split a clean seam (extractable to realizers) or deeply interleaved? Count
  the real coupling points. Is the "task DAG + batch + merge + blocked/deviation" machinery actually
  mode-agnostic today, or shot through with code assumptions (git, pytest, files_changed)?
- Worker invocation (`_run_worker`), batching, `depends_on` prereqs, `phase_result.json` emission,
  tier routing — how tangled with execute specifics?
- The PR #43 question the brief flags as unanswered: can a *decoupled subset* of #43 (worktree
  isolation robustness) ship early independent of the state-write changes, or is it too entangled?
  If you can see the branch/diff, assess; otherwise reason from the files #43 touches.

Key question: is `execute/` a refactorable mode-branched module, or a code-execution monolith where
the "realizer" seam is wishful? AND: is the live PR #43 a foundation risk (a 98-file rewrite of this
exact surface sitting in limbo while we plan to refactor it) — does it need to land/abandon/rebase
BEFORE the unification, or does the unification's instability invalidate #43? Give a clear call.
