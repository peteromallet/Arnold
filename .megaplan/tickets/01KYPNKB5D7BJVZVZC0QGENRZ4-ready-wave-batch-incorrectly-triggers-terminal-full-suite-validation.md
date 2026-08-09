---
id: 01KYPNKB5D7BJVZVZC0QGENRZ4
title: Ready-wave batch incorrectly triggers terminal full-suite validation
status: addressed
source: human
tags:
- bug
- execute
- validation
- recovery
- execution-transaction-integrity
codebase_id: null
created_at: '2026-07-29T10:09:23.117510+00:00'
last_edited_at: '2026-07-31T09:25:00+00:00'
resolution_note: >-
  The terminal-frontier predicate is integrated in the consolidated M11
  lineage. Focused regression coverage proves a non-final ready-wave batch
  skips post_execute_suite, while the archived production attempt advanced
  from batch 23 to batch 24 without launching VJ1. Candidate-ancestor
  `b28eee87669` and
  `test_batch_validation_skips_post_execute_on_non_final_batch` are the
  current code and regression evidence.
addressed_at: '2026-07-31T03:17:11+00:00'
epics: []
---

M11 treated the last batch in a dependency-ready wave as terminal and launched
repository-wide post_execute_suite while T28-T46 remained pending. Historical
run notes cited `0356491baca70ccd362ac680598c881f1ca896c4` and
`5617c401e1a244f7ffd89464f42dfe038279fd44`, but they are not authoritative
candidate ancestry. The current landed implementation is candidate ancestor
`b28eee87669`, and
`test_batch_validation_skips_post_execute_on_non_final_batch` is the exact
regression. Archived attempt 36 remains runtime corroboration: it advanced from
T27 batch 23 to T28 batch 24 without running VJ1.

## 2026-07-31 reconciliation

The fix and its focused regression are present in the consolidated tree
(`tests/execute/test_m8a_execute_wiring.py`). This ticket's complete scoped
acceptance is therefore met; later validation sharding and release-gate policy
remain tracked by 01KYSBGRHM1S8R6RQ1DGZ7843Y rather than keeping this duplicate
symptom open.
