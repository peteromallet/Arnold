# Independent Luna review — Batch 2

You are the one fresh independent GPT-5.6 Luna high-reasoning reviewer for NBF-02 → NBF-03. Read `.oracle/agent_goal.md`, `.oracle/plan.md`, full NBF-02/NBF-03/Batch-2 checkpoint in `.oracle/tasklist.md`, Batch-1 PASS checkin/receipt, and `.oracle/findings/execution-nbf02-nbf03-luna-v3.md` plus receipt. Review current candidate `/Users/peteromalley/Documents/Arnold-oracle-nbf`, branch `megado-nbf-guard-0826`, current implementation checkpoint `19deab5bb407273e7e82d40a66fc06d17af93ad4` with dirty files. Do not implement or mutate source. Write only `.oracle/checkins/batch-2-luna-final.md` and `.oracle/receipts/oracle-nbf02-nbf03-luna-final.md`; temporary evidence under `/tmp` only. Return exactly `RECOMMEND_PASS_BATCH_2` or `RECOMMEND_ACCEPTED_ISSUES` at the start of the checkin.

Run and record exact frozen NBF-02 and NBF-03 pytest commands, authority checker, raw-symbol scan, compile, diff-check, and focused regressions. The v3 executor evidence says NBF-02 242 passed; NBF-03 41 passed/4 failures, with an archived HEAD baseline reproducing the same 4 unchanged legacy babysitter failures. Verify this rather than trusting it. Inspect each acceptance criterion behaviorally: canonical admission before launch, exact live OMP membership/static ox-alpha rejection, native positive proof, fingerprint reservation, T7 no-launch scheduling, controlled launch sequencing/reconciliation, typed terminal transport, exactly-once physical doors including nested OMP, WBC ordering/no-WBC closure, chain/babysitter ownership, and checker negative fixtures. Preserve Batch-1 and identify any new in-scope defect. Bind artifacts to exact current HEAD/diff and record all hashes/timestamps/argv/results. Do not commit/push or start Batch 3.

## North Star — Arnold self-healing supervision

**End state:** An agent harness where no worker can be launched onto a spec that
isn't live, a box that won't survive it, or a seed bound to the wrong interpreter —
and where every worker death carries its killer's identity in a typed record that
the recovery loop consumes before it ever retries the same fingerprint.

**Enduring principles**
- One door per invariant: admission, dispatch, and death are each enforced at
  exactly one place; duplicate preflights are deleted, not patched around.
- Deaths speak: SIGKILL, timeout, terminate, restack — every termination emits
  `{killer, signal, elapsed_s}` into the failure ledger. Silent death is a bug.
- Models are admitted, not assumed: a model id must resolve against catalog,
  prefix map, family classifier, and live provider membership at dispatch time,
  typedly rejecting expired or unknown ids.
- Fixes ship on main through the fixer contract; hotfixes that live only as
  deployed-but-uncommitted files do not exist.

**Anti-patterns to avoid**
- Single-scan verdicts treated as sustained truth (wedge kills, restacks).
- Anonymous integer exit codes where a disposition belongs.
- Judgment-based "healthy" claims without positive proof (live pid + advancing seq).
- Redispatch of an identical failure fingerprint without a changed precondition.

**Aligned progress feels like:** fewer incident classes over time, each new stall
arriving with evidence attached and leaving with a root fix on main.
