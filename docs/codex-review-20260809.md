# Codex adversarial review — fixer-unification implementation (2026-08-09)

Independent validation by Codex (gpt-5.6-luna, read-only) of branch `fixer/fixer-unification-20260807` @ e68be74685 against the design contract (docs/runtime-and-fixer-unification-design-20260807.md §6, megaplan-reference-architecture, megaplan-fixer-briefing).

**Verdict: FAIL — implementation is broad but shallow; production coordination is unwired or non-atomic.**

## Top 5 issues (severity-ranked, with evidence + fix)

1. **CRITICAL — fencing is not actually fenced or deployed.**
   - `acquire_job_lock()` read/decide/write without flock or CAS: repair_lock.py:953-1008. Two contenders both read previous=None, both write epoch=1 with different holder PIDs → same-epoch collision, both can advance.
   - `advance_job_state()` / `acknowledge_job()` similarly read+overwrite without locking (repair_lock.py:1034-1053, :1075-1095); check epoch equality but not holder identity/TTL/liveness; paused same-epoch holder can transition after expiry.
   - Live callers still use `acquire_repair_lock()` (arnold-repair-loop:949-989); trigger uses old lock (arnold-repair-trigger:334-366); scheduler uses separate claim (scheduler.py:285-305). Multiple ownership authorities.
   - Fix: flock/O_EXCL or true CAS around every read-modify-write; bind transitions to holder identity + TTL + liveness; route every fixer through one machine.

2. **CRITICAL — promotion and lifecycle are manual stubs.**
   - `arnold-promote` invokes runtime_manifest CLI subcommands `append_promotion` / `advance_generation` that DO NOT EXIST (runtime_manifest.py:458-498 CLI only has write/read/attest; arnold-promote:148-188 calls fail silently → "NOT advanced").
   - Manual canary/pointer instructions at arnold-promote:182-195; backstop tag printed not pushed at arnold-close:152-158.
   - Fix: implement authoritative CLI subcommands (journal append, canary verification, atomic active-generation pointer switch retaining previous), execute backstop tagging, per-runtime restore evidence.

3. **CRITICAL — manifest authority fails open.**
   - Trigger swallows all manifest errors (arnold-repair-trigger:187-202) → falls back to env/with_name (:187-256); watchdog falls back after parser errors (arnold-watchdog:168-240) and dispatches without `--mode=reactive` (:5190-5222); scheduler converts invalid manifest into `no_pin_configured` SUCCESS (scheduler.py:108-122).
   - Invalid manifests silently skipped; duplicate epic manifests return first match (runtime_manifest.py:251-281).
   - Watchdog selects manifest repair bin but passes SRC_DIR/PYTHONPATH so executable and imported code can come from DIFFERENT runtimes (arnold-watchdog:5238-5267).
   - Scheduler builds wrapper path from its own `__file__` (scheduler.py:162-174) — the exact anti-pattern design line 191 kills — not manifest `epic.repair_bin`.
   - Fix: fail closed after bootstrap when manifest present-but-invalid; bind imported code and scheduler execution to the manifest runtime; use manifest repair_bin everywhere; invoke shadow refusal gate.

4. **HIGH — model and replay gates are bypassable.**
   - Direct model selection + env `*_MODEL` overrides at arnold-repair-loop:133-157 (proactive mode lets CLOUD_WATCHDOG_REPAIR_*_MODEL override Flash — contradicts design line 147 "credentials only, no *_MODEL overrides").
   - `resolve_model_policy` gate is caller-supplied `replay_approved=True` (fixer_model_policy.py:120-141) — no evidence binding.
   - Live replay skipped by default (replay_runner.py:1-9, :178-193).
   - Fix: resolve policy inside the entrypoint; reject model-routing overrides; require evidence-bound replay results before Flash selectable.

5. **HIGH — secret-bearing outputs are unredacted.**
   - `push_base_to_origin` returns credential-bearing `origin_url`, `command_text`, raw stderr (github_sync.py:115-165) — an `https://user:TOKEN@host/...` URL would be echoed.
   - Census `include_values=True` stores raw API keys in public RuntimeProcess (runtime_census.py:214-241, :327-358); test expects "sekrit" to remain (test_runtime_census.py:181-190).
   - Fix: never return raw remote URLs/commands; redact stderr structurally; raw env capture impossible outside isolated diagnostic sink.

## Secondary findings (also fix)

- repair-loop resolves runtime from env paths (:323-337), not manifest; no manifest expected-head check; old lock (:949-989).
- current_target.py:69-92 adds `runtime_attestation` evidence but never refuses; `refuse_shadowed_target` (shadow_attestation.py:247-272) has zero production callers; module resolution inspects reviewer namespace not executing child (shadow_attestation.py:119-131).
- scheduler proactive handler records a plan and marks job successful without launching (scheduler.py:442-460).
- arnold-runtime-create writes manifest with empty venv_path/repair_bin/lockfile/attestation/policy fields (:113-143); writes to ${ARNOLD_RUNTIME_MANIFEST_DIR:-/workspace/markers/runtime-manifests/} — a path launchers never bootstrap from (launchers use /workspace/.megaplan/runtime-manifest.json); no pointer file written.
- arnold-close sets closed before backstop tag / FD/liveness verification / tag push (:112-158).
- arnold-gc-sweep: no schedule-store reconciliation (design says schedule-store-reconciled; probe-4 four trees must-not-GC); restore-proven is a global flag/file, not per-runtime proof (:122-158).
- install_sync: no lockfile-based venv creation, no expected-head verification in sync path (:299-364).
- github_sync: plain push, not expected-old-SHA CAS (github_sync.py:97-165).
- runtime_manifest.advance_generation changes heads in memory only; no canary verify; no atomic active-pointer switch (runtime_manifest.py:396-426).
- fixer_prompt_policy.policy_sha not consumed/verified at dispatch; runtime-create writes empty policy SHAs (arnold-runtime-create:139).
- Tests: no concurrent-acquire race test; launcher tests assert legacy fallback preserved (test_launcher_manifest_conformance.py:53-60) contrary to "kill with_name"; mode tests are string/dry-run asserts; no manifest-failure refusal test, pointer-switch test, schedule-reference GC test, model-policy enforcement test.
> **Authority status: non-authoritative.** This document is historical/design record, not a live-authority operator surface (T44 zero-authority migration).
