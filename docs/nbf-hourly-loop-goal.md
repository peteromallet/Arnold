# NBF Hourly Babysit Loop — Goal Text (v2)

Paste as the recurring message (e.g. `/loop 1h <this text>`). Derived from
`docs/pipeline-babysitting.md` §1 (the hourly check-in is one pass:
**check → fix → push → re-arm**, never just a report) with the fix-the-fixer
exercise made an explicit, numbered part of every fire.

---

## THE FIX-THE-FIXER EXERCISE (run first, every fire)

Before touching anything, reconstruct the last three stalls/failures of this
run from evidence — never from memory:

1. **Collect**: read `docs/nbf-failure-ledger.md` (twin:
   recovery/FAILURE-LEDGER.md on the box), plus current
   `checkin.py` / `direction.py` / newest babysitter receipt / plan
   `events.ndjson` tail / host ftrace sig=15 buffer.
2. **List the last 3 stalls**: what died or blocked, at what time, with what
   fingerprint. If fewer than 3 exist, say so.
3. **Explain WHY each happened** — root cause in one line each (e.g.
   "memcg OOM", "provider timeout SIGTERM", "model key missing"), with the
   evidence pointer that proves it (dmesg line, trace entry, receipt rc).
4. **Ask: is the FIXER failing to fix?** For each of the 3: did a fixer attempt
   engage, and if it failed — was it (a) wrong supervision, (b) premature exit,
   (c) missing tooling/key/model, (d) fixed at source already? If the same
   fingerprint survived a fixer attempt, THE FIXER IS FAILING: escalate to the
   §1.2 loop (swarm → oracle → implement on epic branch → relaunch).
5. **Verdict**: write one sentence — "N stalls in last 24h; k distinct root
   causes, all fixed at source / m unresolved (<which>)".

## IF EVERYTHING IS WORKING

If verdict = all-clean (chain advancing, live worker, no new fingerprints):
- Send a short update: milestone position, last state transition, current
  worker model + age, ETA-ish next phase. No interventions.
- This is the only fire type allowed to be report-only.

## THEN, PER DOC §1.2 WHEN A STALL NEEDS ACTION

Bias toward fixing the fixer, not rescuing the chain:

1. UNDERSTAND — bounded read-only DeepSeek Flash swarm over failure evidence
   (`skills/subagent-launcher/fan.py`). Evidence packs under recovery/<digest>/.
2. RECOMMEND — packed context to codex exec gpt-5.6-sol high-effort, ONE
   foreground call, `timeout --signal=TERM --kill-after=30s 900s … -o
   sol-stage2-proposal.md`. Never background+poll.
3. IMPLEMENT — narrowest source-level fix ON THE EPIC BRANCH
   (fixer/<slug>-<date>); focused regression; persist patch + regression proof.
4. RELAUNCH the fixer (and chain via chain start/resume when evidence
   requires). Never --fresh, no state wipes.
5. VERIFY AT NEXT FIRE — success = last_state left critiqued/blocked AND
   fingerprint does not recur AND live worker ≥10 min with advancing seq.
   PID/prose/self-report ≠ proof.

Escalation trigger (doc §1.1): same fingerprint ~3×, or chain ~1h blocked
without autorecovery, or (added today) a fixer turn that ends without either
proven movement or a written external-gate handoff.

## HARD CONTRACT FOR EVERY TURN YOU SPAWN OR TAKE

- Dead worker + no failure record IS a stall; "operating as expected"
  requires positive proof (live pid + events seq advanced <10 min).
- No turn ends without: proven movement, OR persisted handoff.md naming an
  exact external gate, OR coordination stand-down (different live owner).

## KNOWN TRAPS (act, don't re-diagnose)

- Stale spam tails in babysitter.stdout.log — trust receipts, not log tails.
- "FALSE SUCCESS … failure_fingerprint_unchanged" = FAILURE.
- Model rot: probe target model (`omp models` + live ping) before blaming
  agents. Current pin: glm-5.3-flash everywhere remaining.
- ftrace sig=15 senders named systemd/(sd-pam) are unrelated sessions.
- No `megaplan` binary on PATH; use `python3 -m arnold_pipelines.megaplan`.

## HYGIENE & RE-ARM

- Append new incidents to the ledger every fire that touched a failure.
- Stand down cleanly ONLY when genuinely nothing is blocked and no competing
  fixer owns the occurrence.
- Stop condition: all milestones complete AND chain exits cleanly.
- Otherwise ALWAYS re-arm the next leg before ending the fire.

## PLAN EVOLUTION — feed every failure to the plan (added 2026-08-27)
Whenever a fire touches a failure (new fingerprint, repeated fingerprint, or a
resolved one worth encoding):
1. Write the incident into docs/nbf-failure-ledger.md as usual.
2. Then update THE PLAN so the machinery improves, not just this run:
   - Plan-of-record location: `.oracle/plan.md` in the megado worktree
     (`/Users/peteromalley/Documents/Arnold-oracle-nbf`) — the Grok deep plan.
     Until it exists, the same content lives in `.oracle/agent_goal.md`
     §Objective + `docs/nbf-grok-verdicts.md` §3 (the Grok systemic-guard spec).
   - Feed to the PLANNER (codex exec gpt-5.6-sol high, read-only — or grok-4.6
     when codex is unavailable) a short revision brief: the new ledger entry
     (verbatim), the current plan file (by path), and this instruction:
     "Update the plan based on this failure: either ADD a new DEEP fix task
     addressing the root cause class, or AMEND an existing task/acceptance
     criterion in place. Keep batches/seams coherent. Do not widen scope beyond
     the agent goal. If nothing material changes, answer exactly NO-CHANGE."
3. Record the revision (digest + one-line delta) in .oracle/status.md and in
   the ledger entry (plan-revised: yes/no + where).
This makes every failure a permanent, planned improvement to the pipeline —
not just a patched run.

## ADMIN DISCORD NOTIFY (added 2026-08-27)
On any fire that touches a failure, after the ledger append, send a concise
admin alert: `python3 scripts/discord_admin_notify.py "MESSAGE"` (run on the
agentbox container with hot-env sourced; script reads DISCORD_BOT_TOKEN /
DISCORD_DM_USER_ID from env, falls back to posting <@admin> in the configured
guild channel on DM-403). Message shape: `NBF chain alert (ledger #N): <what
failed> <status/action> <pointer to ledger>`. Also used for pinned-model
decisions requiring approval.
