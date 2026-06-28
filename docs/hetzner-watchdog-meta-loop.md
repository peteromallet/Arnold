# Hetzner meta-loop — supervising the superfixer

Four layers run the epics on the Hetzner box (`159.69.51.216`, container `megaplan-cloud-agent`):

1. **The epic chains** do the actual work (one per repo: `python-shaped-workflow-authoring`, `god-file-splits`, …).
2. **The superfixer** keeps the chains alive + advancing. It is three components that act on their own:
   - **1h watchdog** (`arnold-watchdog`, tmux `watchdog`) — scans every cloud session ~hourly, syncs the editable install, detects stopped/unhealthy/stalled sessions, **background-dispatches a Kimi goal operator** to root-cause + fix + relaunch, and falls back to a direct tmux relaunch if Kimi exits without reviving the session. Writes `/workspace/watchdog-report.json`.
   - **Kimi goal operator** (`arnold-kimi-goal-operator`) — the repair agent the watchdog dispatches; fixes root causes in `/workspace/arnold` on `editible-install`, pushes, refreshes the install, relaunches the affected chain.
   - **6h progress auditor** (`arnold-progress-auditor`) — model-judged (Codex orchestrator + DeepSeek subagents); reviews the last 6h per plan, **fixes** genuine non-critical deadlocks (commit + push to `editible-install`, watchdog relaunches) or **documents** passive ones. Writes `/workspace/audit-reports/`.
3. **This meta-loop** supervises the superfixer — verifies the superfixer is *itself* working across **all** sessions, and **fixes the superfixer** when it is broken. It does not chase individual epics; epic progress is a downstream signal that the superfixer is doing its job.

**The mental model: you are not the watchdog of the epics. You are the watchdog of the watchdog.** When something is wrong, the first question is not "why is the epic stalled?" but "why is the superfixer not catching/fixing that?" — and the highest-leverage action is almost always fixing a superfixer bug at root, not hand-unblocking a single chain.

## What the superfixer should be doing (the bar the meta-loop enforces)

- Scans **every** active session on each tick and writes a **fresh** report (within the last hour; ideally the last few minutes on a healthy box).
- Repairs are **non-blocking**: a Kimi repair on one session must not delay scanning/reporting the others. (The tick background-dispatches repairs via `setsid` and moves on.)
- Every session is either **alive + advancing** (fresh `events.ndjson`, milestones progressing) or **actively under repair** (a Kimi operator running for it, making real progress — not spinning).
- The 6h auditor lands `FIXED <sha>` or `PASSIVE` verdicts and, when it fixes, pushes to `editible-install` (the watchdog then relaunches).

## Each hour, check the superfixer (not the epics)

```bash
ssh root@159.69.51.216 'docker exec megaplan-cloud-agent bash -lc "
  date -u +%H:%M
  # 1. watchdog alive + fresh report
  pgrep -f \"arnold-watchdog\" | grep -v pgrep | wc -l | xargs echo watchdog_procs
  stat -c %y /workspace/watchdog-report.json
  # 2. report covers ALL sessions (sessions_seen should match marker count)
  python3 -c \"import json;d=json.load(open(\\\"/workspace/watchdog-report.json\\\"));print(\\\"sessions_seen=\\\",d.get(\\\"sessions_seen\\\"),\\\"markers=\\\",d.get(\\\"markers_seen\\\"),\\\"issues=\\\",d.get(\\\"issue_count\\\"));[print(\\\" \\\",i.get(\\\"session\\\",\\\"\\\")[:32],\\\"|\\\",i.get(\\\"action\\\"),\\\"|\\\",i.get(\\\"status\\\")) for i in d.get(\\\"items\\\",[])]\"
  ls /workspace/.megaplan/cloud-sessions/ | tr \"\n\" \" \"
  # 3. every session advancing (newest events.ndjson per workspace, fresh = minutes not hours)
  for m in /workspace/.megaplan/cloud-sessions/*.json; do s=\$(python3 -c \"import json;print(json.load(open(\\\"\$m\\\")).get(\\\"session\\\",\\\"\\\"))\" 2>/dev/null); w=\$(python3 -c \"import json;print(json.load(open(\\\"\$m\\\")).get(\\\"workspace\\\",\\\"\\\"))\" 2>/dev/null); echo -n \"\$s: \"; find \$w/.megaplan/plans -name events.ndjson -printf %TH:%TM\\n 2>/dev/null | sort | tail -1; done
  # 4. repairs actually running (and for which sessions)
  ps -eo cmd | grep -oE \"arnold-kimi-goal-operator (god-file-splits|python-shaped-workflow-authoring|[a-z0-9-]+)\" | grep -v grep | sort | uniq -c
  # 5. no deadlock climbing
  grep -c blocked_recovery_not_resolved /workspace/python-shaped-workflow-authoring/.megaplan/cloud-chain*.log 2>/dev/null
  # 6. 6h audit useful
  ls -t /workspace/audit-reports/*.md 2>/dev/null | head -1
"'
```

Read top-to-bottom: time → watchdog procs → report freshness → report covers all sessions → marker list → per-session newest event → which sessions have a repair running → deadlock count → latest audit.

### Green / Red

- **Green**: watchdog alive, report fresh (<1h), `sessions_seen` covers every marker, every session's newest event is fresh (minutes) **or** under active repair, deadlock count flat, audit verdicts landing. The superfixer is minding itself; do nothing.
- **Red**: any of — report stale (>1h) or missing sessions, a session neither advancing nor under repair, a repair running but the session not progressing for a long time, deadlock count climbing, no audit verdicts for >6h.

## Fixing the superfixer (the meta-loop's real job)

When it's Red, the fix is almost always **on the superfixer**, not the epic. Work top-down:

1. **Watchdog stuck / report stale.** A tick should take seconds, not an hour. If the report is stale, the supervisor is wedged. Restart it:
   ```bash
   ssh root@159.69.51.216 'docker exec megaplan-cloud-agent bash -lc "
     pkill -f \"bash /usr/local/bin/arnold-watchdog\"; sleep 2
     setsid bash -lc \"/usr/local/bin/arnold-watchdog >> /workspace/watchdog-supervisor.log 2>&1\" </dev/null >/dev/null 2>&1 &
   "'
   ```
   (Killing the supervisor orphans in-flight Kimi repairs — they keep running, useful work is not lost.) If it goes stale again, there is a **conceptual flaw** — go to step 4.

2. **A repair is spinning (Kimi running but the session not progressing).** The Kimi operator can loop without converging. Kill that one repair and let the watchdog redispatch a fresh one next tick:
   ```bash
   ssh root@159.69.51.216 'docker exec megaplan-cloud-agent bash -lc "
     pkill -f \"arnold-kimi-goal-operator <session> \"
   "'
   ```
   If fresh repairs also spin, that is a superfixer flaw — go to step 4.

3. **A session is neither advancing nor under repair** (the superfixer is not noticing it). Check the report: is the session in `items[]`? If not, its marker is missing/bad or the tick skipped it. Verify the marker at `/workspace/.megaplan/cloud-sessions/<session>.json` and that `kimi_operator_running`/health detection sees it. If detection is broken, that is a superfixer flaw — go to step 4.

4. **Fix the superfixer at root.** This is the highest-leverage action and the whole point of the meta-loop. Root-cause the superfixer bug in `/workspace/arnold` on `editible-install` (Arnold source only — never patch the running chain's project tree), keep it narrow + safe, validate with `bash -n` + the focused test (`tests/cloud/test_watchdog_wrappers.py`), then:
   - copy the changed wrapper to `/usr/local/bin/<wrapper>` + `chmod +x` (the editable-install sync does **not** refresh `/usr/local/bin` — redeploy manually);
   - commit + push to `origin/editible-install`;
   - restart the supervisor (step 1) so the new code is live.
   Example — the serial-tick starvation (one session's 60-min Kimi repair blocked the whole tick, blinding the watchdog to every other session) was fixed by backgrounding the Kimi dispatch (`1ef0e2c6`).

The meta-loop does **not**: hand-merge milestone PRs the superfixer is correctly waiting on, hand-advance a chain the superfixer is about to advance, or patch an epic's project tree. Those are the superfixer's job. If the superfixer is doing them, leave it alone. Only step in when the superfixer itself is broken or blind.

## Cron

This meta-loop runs as a durable hourly cron (off the `:00` mark). Each fire does the check above and fixes the superfixer if Red. The goal is a steady state where every tick reliably keeps every epic alive + advancing without a human — and where, when that breaks, the meta-loop repairs the superfixer rather than the symptom.
