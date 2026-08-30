# Independent Batch 1 review — NBF-01 (GPT-5.6 Luna)

You are the **independent Batch 1 reviewer**, not the executor and not the
Oracle. You are GPT-5.6 Luna. Your job is one complete, evidence-cited review
of NBF-01 against the frozen contract. Do not implement, repair, stage, commit,
push, merge, rebase, reset, or edit production, test, plan, tasklist, North
Star, custody, or existing receipts.

The Grok 4.6 Oracle will store your immutable result at
`.oracle/checkins/batch-1-luna.md`. You **must write that file yourself** as
your only worktree write. Do not write any other path under the worktree.

Worktree: `/Users/peteromalley/Documents/Arnold-oracle-nbf`
Branch: `megado-nbf-guard-0826`
Python: prefer `PYENV_VERSION=3.11.11 python` or the repo venv if present.

## Independence and source identity

Evaluate the candidate against the stated source base, not against later-batch
intent and not against unrelated dirty `.oracle` artifacts.

- Immutable source base: `origin/main@798c50619204010ed3f4297fbb57988fe9381924`
- Candidate branch: `megado-nbf-guard-0826`
- Prepared/planning HEAD (pre-implementation commits, not the NBF-01 code):
  `922241d0bdb3e993c3b554cc69f19948adef7bc3`
- Frozen tasklist SHA-256:
  `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589`
- Settled plan v8 SHA-256:
  `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1`
- North Star SHA-256:
  `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`
- Review scope: **NBF-01 / Batch 1 only**

Independently verify those four SHA-256 digests with `shasum -a 256` on
`.oracle/tasklist.md`, `.oracle/plan.md`, and `.oracle/northstar.md`, and
`git rev-parse origin/main`. If any digest mismatches, that is an issue, not
permission to continue as if frozen.

The NBF-01 candidate is the **uncommitted** owned working-tree plus untracked
owned files. Branch planning commits above `origin/main` are not Batch 1
acceptance evidence.

## Required reads (complete, not summaries)

Read every file below completely before judging:

1. `.oracle/northstar.md`
2. `.oracle/agent_goal.md`
3. `.oracle/plan.md` — complete settled plan v8, especially §§4.4–4.13, §4.16,
   §§4.19–4.21, and NBF-01 at § Batch 1 / NBF-01 (~lines 1969–2106)
4. `.oracle/tasklist.md` — complete NBF-01 section, frozen dispatch/terminal
   semantics, and Batch 1 checkpoint
5. `.oracle/briefs/execution-nbf01-sol.md` — complete Contracts A–G and
   acceptance checklist
6. `.oracle/custody.md`
7. `.oracle/receipts/execution-nbf01-luna.md`
8. `.oracle/findings/execution-nbf01-luna.md`
9. `.oracle/receipts/tasklist-freeze-v8.md`
10. Every owned production and test file listed below

Do not treat the executor receipt as proof. Reproduce the diff and the named
tests yourself.

## Owned candidate paths (NBF-01 only)

Production (may be modified vs `origin/main`):

- `arnold_pipelines/megaplan/orchestration/phase_result.py`
- `arnold_pipelines/megaplan/orchestration/phase_result_classify.py`
- `arnold_pipelines/megaplan/incident/schema.py`
- `arnold_pipelines/megaplan/incident/ledger.py`
- `arnold_pipelines/megaplan/incident/disposition.py` (new/untracked)
- `arnold_pipelines/megaplan/incident/__init__.py` (exports only; confirm no
  extra behavior)

Tests (new/untracked unless noted):

- `tests/arnold_pipelines/megaplan/test_worker_disposition.py`
- `tests/arnold_pipelines/megaplan/test_scheduling_conditions.py`
- `tests/arnold_pipelines/megaplan/test_provider_route_projection.py`
- `tests/arnold_pipelines/megaplan/test_incident_ledger_transactions.py`
- `tests/arnold_pipelines/megaplan/test_reservation_reconciliation.py`
- `tests/arnold_pipelines/megaplan/test_terminal_outcomes.py`
- `tests/arnold_pipelines/megaplan/test_changed_precondition_producers.py`
- `tests/arnold_pipelines/megaplan/test_supervision_confirmation.py`
- existing `tests/arnold_pipelines/megaplan/test_incident_ledger.py`

Any change outside this set, or any later-batch behavior inside it (admission
callers, scheduling loops, T7 waits, T8 thresholds/policy, physical-door
wiring, controlled launch execution, signal-site wiring, provider fallback
decisions, second journal/store/scheduler/rotator), is out of NBF-01 scope.

## Capture the exact candidate diff

From the worktree root:

```bash
git rev-parse HEAD
git rev-parse origin/main
git merge-base HEAD origin/main
git status --porcelain=v1
git diff --name-status origin/main -- arnold_pipelines tests
git ls-files --others --exclude-standard -- arnold_pipelines tests
```

Then capture the owned diff versus `origin/main` for every owned tracked file,
plus `git diff --no-index /dev/null <file>` for every owned untracked file.
Record SHA-256 of that owned unified diff. The executor claimed:

- Tracked owned production diff SHA-256:
  `4aee815d065e6952f1260ef87407c21d40d93eaa70ce232bfea23a15d1519a70`

Independently recompute. A mismatch is an evidence issue unless you can
reproduce the executor's exact hashing method and show it is the same bytes.

Unrelated dirty `.oracle` files and untracked planning artifacts are **not**
Batch 1 acceptance evidence. Note them only as non-owned noise.

## Reproduce every named test command

The executor receipt claims, without persisting pytest logs:

- Focused validation: exit 0, 52 passed
- Legacy regressions: exit 0, 78 passed
- Compile and `git diff --check`: exit 0
- CLI smoke test with a valid worker disposition: exit 0

There is **no** stored pytest transcript under `.oracle/evidence/` for these
runs. Missing output is not permission to assume. Re-run and quote the
verbatim command, exit status, and summary.

Focused command (frozen tasklist / execution brief):

```bash
pytest -q \
  tests/arnold_pipelines/megaplan/test_worker_disposition.py \
  tests/arnold_pipelines/megaplan/test_scheduling_conditions.py \
  tests/arnold_pipelines/megaplan/test_provider_route_projection.py \
  tests/arnold_pipelines/megaplan/test_incident_ledger_transactions.py \
  tests/arnold_pipelines/megaplan/test_reservation_reconciliation.py \
  tests/arnold_pipelines/megaplan/test_terminal_outcomes.py \
  tests/arnold_pipelines/megaplan/test_changed_precondition_producers.py \
  tests/arnold_pipelines/megaplan/test_supervision_confirmation.py \
  tests/arnold_pipelines/megaplan/test_incident_ledger.py
```

Legacy regressions named by the executor finding:

```bash
pytest -q \
  tests/arnold_pipelines/megaplan/test_incident_projection.py \
  tests/arnold_pipelines/megaplan/test_incident_summaries.py \
  tests/arnold_pipelines/megaplan/test_incident_bridge.py \
  tests/arnold_pipelines/megaplan/test_phase_result_classify.py
```

Also re-run the compile command named in the finding, `git diff --check`, and
a CLI smoke test if a valid helper exists. Write pytest output to `/tmp` only;
do not add evidence files under the worktree except the required check-in.

A green pytest run is **necessary but not sufficient**. If tests are thin,
vacuous, or do not cover a frozen criterion, that criterion fails even if
pytest is green. Read every new test module completely and judge coverage
against each acceptance criterion. Count collected tests; if "52 passed" is
mostly pre-existing `test_incident_ledger.py` plus trivial stubs, say so.

## Mandatory dispositions

For **each** NBF-01 acceptance criterion in `.oracle/tasklist.md` (the bullets
under NBF-01 Acceptance criteria **and** the Batch 1 checkpoint bullets), give:

- status: `MET` | `NOT_MET` | `UNEVIDENCED`
- exact file/symbol or missing symbol
- concrete evidence (test name, code snippet location, command output)
- smallest required correction if not `MET`

Cover at least these themes, even if you merge bullets that are literally the
same criterion:

- strict schemas / unknown-field rejection / illegal kind-state combinations
- lossless `DispatchOutcome.kind=worker_disposition` mapping
- single ledger transaction / CAS / no second journal
- changed-precondition producers, evidence binding, single-use consumption
- keyed provider replay (streak increment/rekey/reset/break; probes preserve)
- reservation reconciliation (three resolutions; no blind release)
- two-scan confirmation (TTL, separation, PID/progress/incarnation, single use)
- receipt derivation after append; byte-identical fresh replay
- fail-closed lock/append/schema/projection/cache
- CLI contracts and exact exit statuses 0/2/3/4/5
- `no_launch` produces no worker terminal/fingerprint/provider/breaker state
- TERM vs KILL distinct IDs; OOM requires positive cgroup evidence
- semantic fingerprint and provider-failure key exclude volatile liveness
- different logical IDs with same projection key + fingerprint contend as one
- `provider_route_child_reserved` is one record; no child receipt-ID input
- no excluded later-task file or behavior changed

Then separately evidence-cite:

1. North Star four enduring principles (one door; deaths speak; models admitted;
   fixer contract / no deploy-only hotfix)
2. Each North Star anti-pattern (single-scan truth; anonymous exits; judgment
   healthy claims; identical-fingerprint redispatch)
3. KISS / YAGNI / scope creep: speculative abstractions, duplicate doors,
   ceremonial validation, or later-batch behavior in this candidate
4. Source base, candidate branch, executor receipt, test outputs, diff digest,
   and this check-in path

Take a position. Do not hedge. Missing, contradictory, stale, or unreviewed
evidence is `UNEVIDENCED` / an issue, not a pass.

## Binary recommendation

End with exactly one of:

```text
RECOMMEND_PASS_BATCH_1
```

or

```text
RECOMMEND_ACCEPTED_ISSUES
```

For `RECOMMEND_ACCEPTED_ISSUES`, list each issue with severity
(`blocker` | `major` | `minor`), exact file/symbol or criterion, concrete
evidence, and the smallest required correction. Do not implement corrections.

A recommendation of PASS requires that every NBF-01 acceptance criterion and
every Batch 1 checkpoint bullet is `MET` with cited evidence. `should`-quality
elegance notes may be listed but cannot produce PASS if any frozen `must`
criterion is `NOT_MET` or `UNEVIDENCED`.

## Output file

Write the full review to:

```text
.oracle/checkins/batch-1-luna.md
```

Structure:

```markdown
# Luna independent review — NBF-01 / Batch 1

- Model: GPT-5.6 Luna
- Date: 2026-08-29
- Source base: origin/main@798c50619204010ed3f4297fbb57988fe9381924
- Branch: megado-nbf-guard-0826
- HEAD: <rev-parse>
- Tasklist SHA-256: ...
- Plan v8 SHA-256: ...
- North Star SHA-256: ...
- Executor receipt: .oracle/receipts/execution-nbf01-luna.md
- Owned diff SHA-256: ...
- Focused pytest: exit N, X passed / Y failed (verbatim summary)
- Legacy pytest: ...

## Scope and diff
## Criterion dispositions
## North Star
## KISS / YAGNI / scope
## Issues
## Recommendation
RECOMMEND_...
```

Also print that same recommendation line on stdout as the last line.

Do not write `.oracle/checkins/batch-1-grok.md` or any receipt; the Oracle
owns those. Do not commit.
