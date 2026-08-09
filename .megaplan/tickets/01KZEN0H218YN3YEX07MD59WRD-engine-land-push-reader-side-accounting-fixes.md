---
id: 01KZEN0H218YN3YEX07MD59WRD
title: 'engine: land + push reader-side accounting fixes'
status: open
source: human
tags:
- arnold
- engine
- durable-fix
- codex-plan
codebase_id: null
created_at: '2026-08-07T17:40:52.929840+00:00'
last_edited_at: '2026-08-07T17:40:52.929840+00:00'
epics: []
---

DURABLE ROOT FIX (Codex decision-maker A5). Land/push RT1 commits 095df85d0 (head_sha/code_hash mutable), 9bdc23133+5299c299c (blocked_by_prereq projection), eaf4457d7 (io.py claim-union, aggregation.py scope-exclusion, policy.py medium->light), 72b5b0bd4 (finalize reload scope). Unify the three divergent head resolvers (auto.py:3538, batch.py:1035-1064, chain/__init__.py:2277-2293) onto one ancestor-reconciled resolver. RT1 is 879 commits ahead of origin/editible-install (forked); needs GitHub auth to push.
