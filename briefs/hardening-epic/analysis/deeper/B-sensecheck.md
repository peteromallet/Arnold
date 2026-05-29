# B — Completion-contract shadow mode: adversarial sense-check

**Verdict: Shadow mode is SAFE to leave on for control flow (truly non-blocking,
fail-open, ~30ms/done), but it is NOT trustworthy yet — it will emit
`accepted=False` ("blocked-would-be") on a large fraction of legitimate dones.**
Two false-positive sources (dirty/carried working tree; a real `files_changed`
schema miss) mean the verdict is noisy now and a trap for enforce later. Fix the
worker_did_work bug + scope the diff before anyone reads verdicts as signal or
flips to warn/enforce.

## (a) Real problems / risks — severity ranked

**HIGH — `worker_did_work` ignores top-level `files_changed` (false positive).**
`completion_contract.py:415-425` counts top-level `commands_run`/`sections_written`
but accumulates `files_changed` **only from per-task records**. The real worker
payload writes `files_changed` at the TOP LEVEL (`workers/hermes.py:1348-1353`;
`execute/batch.py:319 payload = dict(worker.payload)`), and `task_updates` records
carry `task_id`/`status`, not necessarily `files_changed`. Verified repro: a batch
with `files_changed:['a.py','b.py']`, `commands_run:[]`,
`task_updates:[{task_id,status:done}]` → `unsatisfied` "no files changed". The
test fixture hides this by putting `files_changed` inside the record. **Fix:** add
`files_changed += len(payload.get("files_changed") or [])` at top level (line ~415).

**HIGH — `landed_diff` false-flags any dirty / carried working tree.**
`LandedDiffProvider` reuses `validate_execution_evidence`, which lists EVERY
working-tree path not in the task's `files_changed` as an "unclaimed change"
finding (`execution_evidence.py:157-165`) → `landed_diff: unsatisfied` →
`accepted=False`. Verified two ways: (1) the m5a carry case — a milestone that
carries prior WIP (`carried.py`) is flagged; (2) any concurrent in-flight run /
unrelated user edit in the shared tree pollutes the diff. `.megaplan/` is
gitignored so plan dirs don't leak in normal runs, but a dirty tree does. In
shadow this is noise; in enforce it is a hard false-block. This is exactly the
SHADOW_TODO base-ref item — but it bites in shadow already as trust erosion.

**MEDIUM — default is `shadow`, ON for every plan with no opt-in.** `auto.py:856`
+ `normalize_contract_mode` default to shadow even when `state.json` has no
`completion_contract_mode` key. Verified: an older/normal plan with no key still
writes `completion_verdict.json` and logs `blocked-would-be`. Given the two FPs
above, every done on this editable install now logs a (frequently wrong)
"blocked-would-be" line and the user's concurrent runs inherit it. Defensible as
the design intent, but consider `off` until the FPs are fixed.

**LOW — `green_suite` flags pre-existing baseline red as `unsatisfied`.**
`completion_contract.py:482-490`: a cached baseline with ANY failing test →
`unsatisfied` → `accepted=False`, with no new-vs-baseline diff (acknowledged TODO).
Most real repos have some red baseline, so this alone flips many verdicts. Noise
in shadow; would be wrong in enforce.

## (b) Things missed

- No test exercises a **realistic** batch artifact (top-level `files_changed`);
  the fixture's record-level shape masks the HIGH bug. Add a fixture matching
  `worker.payload`.
- No test for the **dirty-tree / carried-WIP** false-positive on `landed_diff`.
- `warn`/`enforce` are stubs that log a WARNING and otherwise behave like shadow
  (`auto.py:886-893`, `chain:1056-1064`) — verified they do NOT block today. Good,
  but the WARNING fires on the same false positives, so `warn` is premature.
- `git_base_ref` plumbed through `CompletionContext` but unused — dead until enforce.

## (c) Verified-fine

- **Zero-impact / non-blocking:** both hooks are placed AFTER the outcome is
  decided (`auto.py:1457-1458` inside the terminal branch, return follows
  unchanged; `chain:1526` after PR handling, before `state.completed.append`).
  Both wrap everything in try/except and swallow (`auto.py:894`, `chain:1065`).
  Return values / appended state untouched. Verified by code + the fail-open tests.
- **Never runs the suite:** `GreenSuiteProvider` only reads `finalize.json`
  baseline; `suite_run_in_shadow=False` asserted. No suite invocation anywhere.
- **Latency:** one `git status` (+ bounded nested-repo scan over claimed paths
  only, `loop/git.py:152-167`). Measured 30ms on the real dirty megaplan repo;
  17ms on a small tree. Acceptable per terminal transition.
- **`worker_did_work` reads the right source** (`execution_batch_*.json`, not
  `cli_provenance`) — claim is correct; only the field-level bug above.
- **`from_dict` round-trip fix:** `chain:502-526` adds `completion_contract_mode`
  via `normalize_contract_mode`; `to_dict` includes it (`:473`). 93 `test_chain.py`
  tests pass; round-trip + garbage-normalization tested.
- **Test count:** 11 (not 15). All pass. They exercise REAL providers + REAL
  `auto._shadow_completion_verdict` (real git repos, real `validate_execution_evidence`),
  not over-mocked — but with unrealistic batch fixtures (see (b)).
- Waiver logic (`compute_verdict:638-649`) correctly excuses `landed_diff`/
  `worker_did_work` only; tested.

## (d) Concrete fixes

Before trusting verdicts on a live install (shadow):
1. **Count top-level `files_changed`** in `WorkerDidWorkProvider` (1-line, kills
   the HIGH false positive). Add a realistic-payload test.
2. **Scope `landed_diff` to claimed-or-base diff**, or in shadow downgrade the
   "unclaimed changes" finding to non-blocking / `unknown` on a dirty tree, so a
   dirty/carried tree doesn't read as `unsatisfied`. Add a carried-WIP test.

Before warn/enforce:
3. Implement the per-milestone base-ref (`base..HEAD`) diff — without it both the
   dirty-tree and carry false-blocks are fatal.
4. `green_suite`: compute NEW-vs-baseline; don't block on pre-existing red.
5. Gate the WARNING in `warn` mode behind the FP fixes (today it cries wolf).

Optional now: default to `off` (or keep shadow but silence the
`blocked-would-be` log line) until 1+2 land, to avoid eroding trust.
