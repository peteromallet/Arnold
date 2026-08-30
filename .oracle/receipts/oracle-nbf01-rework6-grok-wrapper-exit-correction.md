# Append-only correction — NBF-01 attempt-6 Grok wrapper evidence

This is executor bookkeeping evidence, not a new Oracle review or verdict. It
corrects the process-exit interpretation around the already-written attempt-6
Grok artifacts without modifying either historical artifact.

## Primary wrapper record

The primary Grok 4.6 wrapper was launched from the repository with this exact
command:

```text
/bin/zsh -lc 'python /Users/peteromalley/.claude/skills/subagent-launcher/launch_omp_agent.py --model=grok-4.6 --query-file=/Users/peteromalley/Documents/Arnold-oracle-nbf/.oracle/briefs/oracle-nbf01-rework6-grok.md --project-dir=/Users/peteromalley/Documents/Arnold-oracle-nbf --timeout=3600'
```

- CWD: `/Users/peteromalley/Documents/Arnold-oracle-nbf`
- Unified command-execution record: `46816`
- Observed launcher process: PID `99149` (the Python `launch_omp_agent.py`
  process); observed provider child: PID `99180` (`bun ... omp -p --model
  grok-4.6 --no-session`)
- Start: `2026-08-30T05:52:35.208Z`
- End: `2026-08-30T06:23:07.621Z`
- Duration: `1832.383233500s` (`1832s` + `383233500ns`)
- Wrapper exit: `1`
- Provider result: HTTP `403`,
  `You have run out of credits or need a Grok subscription. Add credits at
  https://grok.com/?_s=usage or upgrade at
  https://grok.com/supergrok. (type=personal-team-blocked:spending-limit)`

The captured streams are accounted for separately from the repository
artifacts:

| stream | bytes | SHA-256 |
|---|---:|---|
| stdout | 431 | `0b3a728a151ab5503143bf311799a41ce82849e9cf0dc2cb2b65f951490a42c8` |
| stderr | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |

## Artifact timing and interpretation

The Oracle PASS artifacts were complete before the failed wrapper return:

- `.oracle/checkins/batch-1-rework6-grok.md` was created/observed at
  `2026-08-30T06:21:59Z`; stable SHA-256
  `1a3cac2973d67ea270bd324ee742fcd074a696bff49ab55cd7e20b9aaa8d6b79`.
- `.oracle/receipts/oracle-nbf01-rework6-grok.md` was created/observed at
  `2026-08-30T06:23:06Z`; stable SHA-256
  `5ede0d4cf30e0cef5c1dfbdf6fab7aed36269e818b1122bac3def59928e0832a`.
- The check-in begins with and records the completed Oracle token
  `PASS_BATCH_1`; the receipt records the same PASS before the wrapper's
  `06:23:07.621Z` failed return.

The exit-0 record in the existing receipt belongs to the exactly-one
commissioned GPT-5.6 Luna/high independent reviewer only. It is not the exit
status of the primary Grok wrapper. No second reviewer, fanout, replacement,
or tiebreaker was launched.

The audit establishes completion ordering and stream/process evidence. It does
not establish an atomic-rename protocol, so no atomic-rename claim is made
here.

## Separate direct Grok activity

The audit also recorded a separate earlier direct Grok 4.6 invocation for the
attempt-6 *triage* brief, kept separate from the primary-wrapper accounting:

```text
python /Users/peteromalley/.claude/skills/subagent-launcher/launch_omp_agent.py --model=grok-4.6 --query-file=/Users/peteromalley/Documents/Arnold-oracle-nbf/.oracle/briefs/rework-triage-batch-1-attempt-6-grok.md --project-dir=/Users/peteromalley/Documents/Arnold-oracle-nbf --timeout=3600
```

That process tree was launcher PID `52973` with `bun` child PID `53004`, ran
from `2026-08-30T05:08:45.544Z` through `2026-08-30T05:20:39.251Z`
(`713.706958750s`), and exited `0`. Its output explicitly said triage only,
no Luna/review dispatch, and no Batch-1 token; it wrote only the triage packet
and triage receipt. It is not a second reviewer and is not evidence that the
primary Grok wrapper exited successfully.

Recorded after the Batch-1 PASS checkpoint; source, tests, frozen tasklist,
North Star, status, goal, custody, and historical receipts were not changed by
this correction.
