---
id: 01KYPNKB5D7BJVZVZC0QGENRZ4
title: Ready-wave batch incorrectly triggers terminal full-suite validation
status: open
source: human
tags:
- bug
- execute
- validation
- recovery
- execution-transaction-integrity
codebase_id: null
created_at: '2026-07-29T10:09:23.117510+00:00'
last_edited_at: '2026-07-30T12:58:47.833492+00:00'
epics: []
---

M11 treated the last batch in a dependency-ready wave as terminal and launched repository-wide post_execute_suite while T28-T46 remained pending. The terminal-frontier fix is active at 0356491baca70ccd362ac680598c881f1ca896c4, with equivalent preserved commit 5617c401e1a244f7ffd89464f42dfe038279fd44. Proof: attempt 36 advanced from T27 batch 23 to T28 batch 24 without running VJ1. Preserve the focused terminal-frontier regression when folding this fix.
