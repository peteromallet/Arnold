# Census S1–S4 — manifests, recorded roots, live imports, wrapper provenance

Collected: 2026-08-11 (UTC, read-only SSH into box container megaplan-cloud-agent-resident-only).
Evidence SHA: see receipts in docs/fixer-recovery-evidence/. No mutations performed.

## S1 — Runtime manifests

| Manifest | runtime_id | state | schema | notes |
|---|---|---|---|---|
| `/workspace/.megaplan/megaplan-maintenance.json` | megaplan-maintenance-20260811 | active | 1 | ONLY real per-epic manifest. base.commit=f410585d56, editable_install_path="", epic.branch=fixer/megaplan-maintenance-20260811, epic.expected_head=f410585d56, epic.runtime_root=/workspace/runtime-candidates/megaplan-maintenance, epic.repair_bin=<root>/arnold_pipelines/megaplan/cloud/wrappers/arnold-repair-loop, epic.venv_path=<root>/.venv (DOES NOT EXIST), indirection.verified_head=f410585d56, generation=1 |
| `/workspace/.megaplan/9b319e-shannon-b-prepare.json` | — | — | arnold.megaplan.shannon_dependencies.v1 | NOT an epic runtime manifest (deps probe artifact) |
| `/workspace/.megaplan/9b319e-shannon-b-probe.json` | — | — | arnold.megaplan.shannon_dependencies.v1 | same |
| `/workspace/.megaplan/cloud-status-snapshot.json` (+ .previous) | — | — | null | legacy status dump, Jul 6, zero writers/readers (W2) |

## S2 — Recorded engine_roots (metadata.execution_environment.engine_root per chain)

| Chain | engine_root | Class |
|---|---|---|
| critique-ledger-accountability-v2-20260728 | /workspace/runtime-candidates/arnold-c7bcb06af536acfe759c1b31a785afc19afe92d4 | MISSING |
| critique-ledger-accountability-v3-20260803 | null | NULL |
| v3-r2-20260803 | /workspace/runtime-candidates/arnold-d9dfab4c80835829ec1e1218f0e1f9c84071482e | MISSING |
| v3-r3-20260803 | /workspace/runtime-candidates/arnold-82a5a012fa58f44cdc5e9e895f454d86d95b446d | MISSING |
| v3-r4-20260803 | same arnold-82a5a012... | MISSING |
| v3-r5-20260803 | /workspace/runtime-candidates/arnold-wbc-full-20260804 | CONFLICTED (UU attempt_ledger_store.py, DU worker_dispatch_wbc.py, DU UNFINISHED_WORK.md) |
| v3-r6-launch-20260805 | /workspace/runtime-candidates/arnold-r6-launch-20260805 | MISSING |
| v3-r7-launch-20260805 | /workspace/runtime-candidates/arnold-r7-fresh-child-20260805 | PRESENT + SHARED (hot-patched, .bak-*) |
| critique-ledger-bigbang-20260716 | /workspace/arnold-runtime-b92380231941-r2 | MISSING |
| custody-control-plane-20260714 | /workspace/runtime-candidates/arnold-5bf11d5a5600 | MISSING (also chains referencing runauthority editable-engine) |
| custody-control-plane-m10-stable-20260726 | /workspace/runtime-candidates/arnold-92aee9982bd2f99dad6c24166c130d1fa4db9b14 | MISSING |
| discord-resident-lifecycle-corrective-20260710 | <proj>/.megaplan/runtime/editable-engine | EMPTY SHELL |
| megaplan-maintenance | /workspace/runtime-candidates/arnold-r7-fresh-child-20260805 | PRESENT + SHARED + SPLIT (manifest binds epic worktree f410585d56) |
| megaplan-native-parity-corrective | /workspace/arnold | PRESENT (dirty resident tree, 30 files) |
| repository-strategy-roadmap | /workspace/arnold-consolidation-20260714 | MISSING |
| runauthority-epic-all-codex | <proj>/Arnold | project root itself |
| runauthority-epic-cloud / epic / sprint-1 | <proj>/.megaplan/runtime/editable-engine | EMPTY SHELL |

**Dangling roots total: 9** (c7bcb06a, d9dfab4c, 82a5a012 ×2, r6-launch, b9238023, 5bf11d5a, 92aee998, arnold-consolidation). Plus 4 empty editable-engine shells (discord-resident-lifecycle-corrective-20260710, runauthority-epic-cloud, runauthority-epic, runauthority-sprint-1) + 1 broken worktree gitdir (critique-session-binding-20260723 → parent arnold-bc0c600c GC'd).

## S3 — Actual import roots (python -c 'import arnold_pipelines; print(__file__)')

- Supervisor venv python (`/workspace/runtime-venvs/arnold-4ed98585...-live/supervisor/runtimes/b6e1a666.../bin/python3`, NO PYTHONPATH): `/workspace/arnold/arnold_pipelines/__init__.py` → resident tree @ 3299a4f0 (dirty)
- Same interpreter WITH watchdog env (PYTHONPATH=/workspace/omp-replaces-hermes/Arnold): `/workspace/omp-replaces-hermes/Arnold/arnold_pipelines/__init__.py` → watchdog tree @ 0cc5ffb6
- Chain execution (recorded engine_root + traceback): `/workspace/runtime-candidates/arnold-r7-fresh-child-20260805/arnold_pipelines/megaplan/...` → engine candidate @ 7f6abcbe42
- Epic worktree (`/workspace/runtime-candidates/megaplan-maintenance`): fixer/megaplan-maintenance-20260811 @ f410585d56; `.venv` DOES NOT EXIST so no interpreter can import from it as a venv; PYTHONPATH=<root> would import its tree

**Four-tree split confirmed**: engine candidate 7f6abcbe42, epic worktree f410585d56, watchdog tree 0cc5ffb6, resident tree 3299a4f0 (30 dirty files) — three different "main"s.

## S4 — Wrapper provenance

- `/usr/local/bin` writers: (a) image build `COPY wrappers/ /usr/local/bin/` (cloud/templates/Dockerfile:118) — build-time; (b) the ONLY observed live post-build updater is `arnold-watchdog:2126-2148 sync_cloud_runtime_wrappers()` — copies `$SRC_DIR/arnold_pipelines/megaplan/cloud/wrappers` → `/usr/local/bin`, `cmp -s` idempotent, `install -m 0755`, called every sweep + relaunch (ensure_install_or_repair:2435). Wrapper drift is a downstream symptom of tree-selection split-brain, not independent stale copies. (Narrowed per G1: Dockerfile is a build-time writer.)
- **Measured wrapper drift (2026-08-11):** SHA-256 of `/usr/local/bin` vs the engine tree (`arnold-r7-fresh-child-20260805/.../wrappers`):

| Wrapper | /usr/local/bin | engine tree | match |
|---|---|---|---|
| arnold-watchdog | 985c4e945fb6476d16ae78a09ad593aea5472a99016e8c0c7a253ca13f58fda3 | f50bbf31dbd45eae5014f43923c56ff151d6c7c125e20c0871d755f0d487cba0 | NO |
| arnold-repair-loop | 89debf5899b7b8cfe43459ab3f7b49f0378eba1a649979b73e894feebe941afb | ed02b6ffed09cee7f4ebd2742575dadc50b8642c90d85b80f368d03d8d6dfb53 | NO |
| arnold-repair-trigger | c54a2030b071f8070a3996ed65add3f3109322a257bed56108f21689964f5592 | 5906c4bdd691f055fa7ced652eb20a348b5ebd1996a1abdbe1cdaca91b097724 | NO |
| arnold-meta-repair-loop | 0900f59ee472d063afc2d60ee34a8fe184d569fb40f64d7e7111abe5f7edd78d | 87aaec10d54ea64e060a7b31a6d3343732d04743f990aa3f5ae9f011a00ac18c | NO |
| arnold-runtime-create | 6525a01104232f70ae97b9f2fbb6b2c0e93631be8b08760142f79d929efacdb6 | 6525a01104232f70ae97b9f2fbb6b2c0e93631be8b08760142f79d929efacdb6 | YES |

  → 4 of 5 installed wrappers do NOT match the executed engine tree. The
  installed copies were synced from a DIFFERENT source tree (whichever SRC_DIR
  the watchdog imported at its last sync), confirming wrapper drift is real and
  live. Classified NON-GREEN.
- Engine candidate `arnold-r7-fresh-child-20260805` carries untracked `.bak-*`: arnold-repair-loop.bak-merge, arnold-watchdog.bak-statusfix, arnold-watchdog.bak-superfixer-only, batch.py.bak-shadow, partnered-5-glm.toml.bak-20260807, subagent.py.bak-summarizer, render_goal.py.bak-edit20260807. Live tracked files == HEAD @ 7f6abcbe42 (porcelain clean except untracked .bak).
- Wrappers identical between 7f6abcbe42 and local main 53584bb018 (empty diff).

## Coherence verdict

Every mismatch above is classified NON-GREEN: recorded engine_root ≠ manifest runtime_root (megaplan-maintenance), recorded roots dangling (9), executed root shared across epics (v3-r7 + megaplan-maintenance), resident tree dirty, epic venv missing. No green runtime identity exists for any active/paused chain.
