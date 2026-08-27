# NBF P0 Failure Ledger — living doc

Occurrence chain for plan `p0-mrc-closeout-intake-and-20260826-0049`
(epic `native-build-forward`, digest lineage `1ac805e5eef9` → …). All times UTC.
Sources: container `/tmp/watchdog-ensure.log`, babysitter receipts + stdout/stderr,
plan `events.ndjson`, plan `state.json latest_failure`, host `dmesg -T`,
host ftrace `/sys/kernel/tracing/trace` (sig==15), local Arnold commits.

## 2026-08-26 failures (chronological)

| # | When | What died / failed | Root cause | Class | Fix | Status |
|---|------|--------------------|-----------|-------|-----|--------|
| 1 | 00:49→01:17 | plan born; revise dispatch 1913264 (ox-alpha) starts then dies | memcg OOM kill of omp (`dmesg` 01:24:52, 76 GB virtual) — SIGKILL uncatchable → no failure record | resource | 16:xxZ `docker update --memory 16g`; commit `5fa0d32e76` on NBF (survive cgroup-killed phase workers) | FIXED |
| 2 | 01:17–10:30 | P0 sits dead ~9h, no fixer engages | watchdog env-pinned to megaplan-maintenance session + restack churn every minute + babysitter launch hung importing via supervisor venv python | machinery | marker-scoped observer, in-flight sweep guard, interpreter pin 3.11 (commits 1916884270-era, deployed 10:33Z) | FIXED |
| 3 | 11:23 → 11:28 | revise redispatch v4-pro worker 2384793 dies silently | same memcg OOM (`dmesg` 11:28:07 python 5.8 GB) | resource | same as #1 | FIXED |
| 4 | 10:34→10:57 attempt A1 | fixer turn dies rc=-15 at 1406s, silent | launcher/harness per-turn subprocess timeout sends SIGTERM (proven by later stdout `done in 1401.9s exit=143`) | self-timeout | commit `41bdef47aa` default 1800→7200 + `MEGAPLAN_TURN_TIMEOUT_SECS` | FIXED |
| 5 | 17:04 / earlier | fixers on ox-alpha fail instantly: `Model "openrouter/stealth/ox-alpha" not found` | model expired (provider removed); no usable key route | model rot | switched to openrouter/deepseek-chat → glm-5.1 → **glm-5.3-flash** (pin) | FIXED |
| 6 | 18:58 | fixer turn ends 118s writing handoff "missing tools" | false verdict: invoked nonexistent `megaplan` binary; never probed `python3 -m arnold_pipelines.megaplan` | prompt gap | goal TOOLING note + HARD TURN CONTRACT `167e5f7b08`/`00d956eae1` | FIXED |
| 7 | 13:46+ several | attempt finishes claiming "chain operating as expected" while checkin shows dead worker | goal allowed judgment-based healthy verdict without proof | prompt gap | HARD TURN CONTRACT items 1–2 (proof standard: live pid + seq delta <10 min) | FIXED |
| 8 | 14:2x | gate deterministic fail 3× `runtime_launch_attestation_mismatch: canonical seed missing` when run outside cloud dispatch wrapper | seed lives in dispatch-current.json pointed path; direct invocations lacked `MEGAPLAN_RUNTIME_LAUNCH_SEED` | identity/env | resolved within superfixer attempts via wrapper relaunch (seed propagated through supported seam) | RESOLVED |
| 9 | 14:2x–19:4x | finalize fails 3× `critique_finding_unresolved CF-53349D3C` → state blocked | content: revise must traceably resolve or invalidate flag; blocked needs fingerprint-bound recovery | chain content | glm fixer recovered (blocked→planned 20:06Z); resume drove fresh critique | RECOVERED |
| 10 | evening cycles | premature exits after 84s/7.8s "verdicts" | see #7 (pre-contract) | prompt gap | covered by contract | OBSERVED-FIXED |
| 11 | recurring | stale stdout spam: 64k lines `Model not found` from Aug 25 wrong-cwd era appended to active run logs | append-only logs reused across eras mislead readers | observability | accepted cosmetic trap; documented here + direction.py reads receipt not tail | DOC'D |

## Current open items
- [ ] P0 still pre-execute as of 20:59Z; glm-5.3-flash fixer `12f5e50e0107` running codex consult (started ~20:58).
- [ ] `MEGAPLAN_SUPERVISOR_SOURCE_ROOT: unbound variable` noise in babysitter stderr (cosmetic, env seam).
- [ ] Sweep `ModuleNotFoundError: wrappers.repair_delegation` each scan (import-path defect; ticket).
- [ ] `~z-ai/glm-latest` / provider catalog drift generally: add catalog drift alarm so model expiry is caught at dispatch time, not via instant-exit loops.

## Verification rule (§1.2)
Movement = `last_state` leaves critiqued-park AND failure fingerprint does not recur
AND a live worker exists ≥10 min with advancing events seq. PID/prose ≠ proof.
| 12 | 21:05–22:33 | three more silent fixer deaths (770s/1406s/124-style) + one live turn on EMPTY --model hitting `omp_rpc host_tools unavailable` ×3 | stacked regressions: G14 rewrite dropped identity-prefix tail-return AND reset-hard cycles reverted deployed fixes; hot-env ox-alpha pin overrode model all night | mixed | ftrace attribution -> wedge two-scan confirm a344ab833e; catalog+pin commits; hot-env pins rewritten to bare glm-5.3-flash id (survives resets); launcher redeployed from fresh main; bad-model turn killed for clean redispatch | IN PROGRESS |

## Watch-item resolution log
- 2026-08-27 ~11:54Z: p1 `finalized→execute` transition completed autonomously after
  ~35 min of executor activity; chain cursor advanced into idx-1 execute. No seam
  nudge used. Clock-frame note: container reports true UTC (`date -u`); earlier
  ledger lines mixing local-tagged times should be normalized when computing gaps.
