# Megaplan Cloud stability audit — 2026-07-19

## Verdict

The last clearly repeatable completion window was **2026-07-13 23:50 UTC through 2026-07-14 19:42 UTC**, the Arnold `repository-strategy-roadmap` chain. It completed **5/5 consecutive milestones** without a terminal restart. The chain began with an independently verified editable runtime at:

`e894881275e7d6587ee888928ce088af71ae64e9` — `Fix runtime mirror editable-install fetch`

This is the recommended recovery base. It is still an ancestor of `origin/editible-install`, so a clean clone can fetch it. Use the exact SHA, not the moving `editible-install` name.

The runtime was refreshed twice while that chain ran (`91a33dab...` at 2026-07-14 05:12 and `616d5bb...` at 15:40), so the entire 5/5 outcome cannot honestly be attributed to one SHA. `e894881...` is nevertheless the best rollback point: it launched the clean chain, completed its first milestone and most of its second, fixed the editable-runtime mirror itself, and is reachable from the current remote branch. By contrast, `616d5bb...` immediately preceded the next chain's `editable_runtime_import_root_mismatch` failures, and `91a33dab...` is no longer on the current branch ancestry.

## Evidence

Outcome is taken from each plan's authoritative `.megaplan/plans/<plan>/state.json` and `meta.chain_completion`, with cloud-chain logs used for engine provenance. Supervisor/watchdog process exit codes are not treated as sprint outcomes: a watchdog invocation can return nonzero after a milestone has published or while deciding whether to relaunch, and several such logs contradict the durable `done`/chain-completion records.

| Run / repo | Window (UTC) | Outcome | Verified engine revision(s) | Failure class / qualification |
|---|---:|---|---|---|
| Reigh composition-spine epic (`reigh-app`) | Jul 1–5 | 13/13 chain milestones reached `done` (14 terminal plan records because M2 was restarted) | final observed refresh `c663821e`; earlier revision not recorded in the log | Some finalize-scope and publish callback recovery; still the strongest long completion streak. |
| Megaplan native-parity corrective (`Arnold`) | Jul 5–8 | 7/7 chain milestones eventually completed, but repeated abandoned/restarted plans | initial observed `9c92ce66`; branch moved during run | Empty Hermes JSON, provider 429, Codex stalls, multiple blocked/failed restart plans. Not a clean baseline. |
| Extension-reality convergence (`reigh-app`) | Jul 7–8 | 4/4 completed | `81f9d747` → `29b871bd` → `02b2a17a` → `2e073a8b` → `35814319` → `5ae18b5f` | Several 600s Codex stalls and resume fixes landed during the run. Completed, but self-repaired. |
| Runauthority cloud (`Arnold`) | Jul 10–11 | 3/3 completed | `74dd75854` at launch, runtime mirror changed to `7fe6fef0` before final execute/review | Review-schema retries (`north_star_actions`) and Codex limits; completion was consistent at sprint level but engine provenance was mixed. |
| Repository-strategy roadmap (`Arnold`) | Jul 13 23:50–Jul 14 19:42 | **5/5 consecutive milestones completed** | **`e894881275...`** → `91a33dab28...` → `616d5bb839...` | Last clean chain. No terminal restart; one blocked execute was correctly continued from completed finalize state. |
| Custody control plane (`Arnold`) | Jul 14 onward | M5 done after repair; M5a took ~58h; M6 remained `finalized`, not chain-complete | `616d5bb839...` then at least 20 runtime revisions through `f038f49c...` | Immediate immutable runtime/import-root drift, repeated callback failures, stalls, continuous hot runtime replacement. Clear instability boundary. |
| Critique-ledger bigbang (`Arnold`) | Jul 16–17 | 0/1 complete; plan `paused` at gate | `17a7ce97f2...` | Gate structural enum mismatch plus missing/restored corpus dependency. |

Current `origin/editible-install` is `14912c118122d1beb2eaeceeb6ec9c19c6e3cfbe` (2026-07-15 12:48 UTC), **115 commits after** `e894881...`; for `arnold_pipelines/megaplan` alone that range is about **38,473 additions / 1,764 deletions across 150 files**. The cloud worker is currently importing from a later special-purpose worktree, not `/workspace/arnold`, which further weakens the branch name as runtime provenance.

## Recommended cloud layout

Do not edit the same checkout that supplies the running Megaplan interpreter. For Arnold-on-Arnold work, use two checkouts:

1. **Immutable engine checkout:** `/workspace/arnold-engine-e894881` detached at exact SHA `e894881275e7d6587ee888928ce088af71ae64e9`; install this with `pip install -e` and verify `import_root == source_root` and `runtime_revision == expected_revision`.
2. **Editable target checkout:** `/workspace/arnold-next` on a new branch based at `e894881...`; Megaplan edits this project tree, never the engine tree.
3. Set each cloud run's engine ref to the exact SHA. **First fix or bypass `_megaplan_refresh_command`, which currently hardcodes `editible-install` instead of honoring `spec.megaplan.ref`; config-only SHA pinning is not reliable until that is corrected.** Do not point an in-flight chain at a moving branch, and disable any watchdog/auditor behavior that hot-refreshes the engine during the run.
4. First canary: one nontrivial sprint in a non-Arnold repo. Second canary: a three-milestone Arnold chain. Require three consecutive `done` milestones, no manual state edits, no runtime refresh, and no callback/repair restart before promotion.
5. Bring later Megaplan changes over from `e894881...` in small, themed batches. After each batch, run the same canaries and record the exact SHA. This yields a bisectable promotion ladder.
6. Only after the canaries pass should a named stable branch (for example `megaplan-engine-stable`) advance to that SHA. Keep `editible-install` as the development/integration lane until active chains are drained; do not force-move it underneath live runs.

## Caveats

- This is observational evidence, not a controlled benchmark: model quotas and provider stalls account for some failures.
- A chain marked `done` can include recovered phase errors. The recommendation weights uninterrupted consecutive milestone completion and runtime provenance more heavily than the terminal state alone.
- `e894881...` predates useful later fixes. The safe strategy is stable-base plus selective promotion, not permanent rollback.
