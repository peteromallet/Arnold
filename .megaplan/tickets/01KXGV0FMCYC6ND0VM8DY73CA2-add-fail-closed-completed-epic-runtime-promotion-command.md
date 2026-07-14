---
id: 01KXGV0FMCYC6ND0VM8DY73CA2
title: Add fail-closed completed-epic runtime promotion command
status: open
source: human
tags:
- tech-debt
- automation
- provenance
- safety
codebase_id: null
created_at: '2026-07-14T17:32:48.141161+00:00'
last_edited_at: '2026-07-14T17:32:48.141161+00:00'
epics: []
---

There is no single supported command that turns durable completed-chain evidence into a canonical-main landing, refreshes the actual interpreter editable install, verifies import and content provenance, and writes a content-addressed receipt. Compose the existing chain verify and manifest evidence, GitHub expected-head non-force merge, cloud runtime_provenance, install_sync, and runtime promotion receipt primitives rather than adding another competing path. The command must identify the result revision from durable chain and plan evidence; require a clean isolated integration worktree; reject dirty or concurrently written targets, incomplete or stale PR state, remote-tip drift, conflicts, protection and approval gates, and non-ancestor landings; run focused and target integration tests; install with the discovered sys.executable; verify distribution direct_url, imported arnold and arnold_pipelines roots, landed Git revision, and content identity from a neutral cwd with unsafe path injection disabled; emit an atomic receipt containing source revision, landed revision, remote and branch, interpreter, editable root, import paths, tests, timestamps, and hashes; be idempotent and never stash, reset, force-push, delete, or restart services. Add focused conflict, concurrent-writer, stale-tip, provenance-shadowing, and idempotency tests plus operator docs.
