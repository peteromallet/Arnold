# Status — megado run on Arnold
- Phase: 5 executing. B1-B4 PASS (+reworks closed). B5: T8a gate PASS, T8b implemented, rework attempts 1-5 (custody hardening loop), attempt-5 in flight.
- USER-AUTHORIZED DEVIATIONS (2026-08-21):
  - [XHARD] class switched to openrouter:stealth/ox-alpha (probe verified); oracle stays Sol.
  - Batch gate relaxed: B6+B7 share one combined oracle gate (was per-batch).
  - B6 parallelism authorized: T9 (Luna) and T10 (stealth) run concurrently; T10 codes against the frozen five-file contract, integrated at the B6 checkpoint.
- Base: 744a417198 · foundation b7c682798e · contract eac81e57d2 · plan 796961cd9c · tasklist fde620d21d
- Commits: B1 9224f52ce2 · B2 fd4f58b77a+1d9dc17f60 · B3 97bf1264c5+028cf9db97+f3bdcb9635 · B4 f4122bbebe+42f86de734+c522810273 · B5 c0c3af88a0(T8a)+902a2a46dd(T8b)+rework commits
- Blockers: none in-run. Main-tree purge (bg_7) timed out mid-edit — post-run resolution owed to user.
