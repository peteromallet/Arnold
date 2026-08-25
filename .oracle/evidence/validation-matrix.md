# Validation matrix — first-run provider onboarding (megado Batch 5)

Maps every agent_goal done criterion and every North Star principle to concrete
evidence. All commands run from the worktree root
(`/Users/peteromalley/Documents/Arnold-onboard-oracle`, branch `onboard-oracle`).
Nothing committed; tree left dirty for final oracle review.

## Evidence index

| File | What it is |
|---|---|
| `.oracle/evidence/b5-a-pytest-onboarding.txt` | Battery (a): targeted onboarding suite, verbatim |
| `.oracle/evidence/b5-b-pytest-regression.txt` | Battery (b): affected regression subset, verbatim |
| `.oracle/evidence/run_e2e_onboarding.py` | E2E script (batteries c/d/e), reusing test-fixture seams with REAL wire/persistence |
| `.oracle/evidence/e2e-transcript-launch1.txt` | Full captured transcript of scripted launch #1 |
| `.oracle/evidence/e2e-secret-scan.txt` | [W1/R3] secret scan verdicts |
| `.oracle/evidence/e2e-models-yml-redacted.yml` | Merged models.yml snapshot (fake key value redacted) |
| `.oracle/evidence/e2e-home-check.txt` | [W1/R4] `$HOME`-expansion verdict |
| `.oracle/evidence/e2e-persistence-proof.txt` | Two-launch persistence proof |

## Agent goal — done criteria

### D1. Fresh-launch simulation triggers the offer on a TTY and completes to one verified route; declined/non-TTY paths produce today's typed failure unchanged
- **Command:** `uv run pytest tests/agentbox -q -k onboarding`
- **Result:** `122 passed, 1 skipped, 318 deselected in 228.93s (0:03:48)`, exit 0.
  Covers: happy-path flow session completes to a verified route (`test_onboarding_flow.py`),
  decline → cancelled, EOF mid-flow → exit 1, non-TTY → exit 2 + one-line hint;
  guard-matrix + golden-file non-TTY byte-identity (`test_onboarding_triggers.py`);
  old-pin fallback (`FileNotFoundError`/`OSError` ⇒ original failure path untouched);
  E2E launch #1: `exit_code=0 verified=True provider=deepseek route=deepseek/deepseek-v4-flash`
  (`.oracle/evidence/e2e-secret-scan.txt` lines 2–4).

### D2. Wired route survives a NEW process (persistence proof): second launch runs with zero prompts
- **Command:** `uv run python .oracle/evidence/run_e2e_onboarding.py`
- **Result:** PERSISTENCE_PROOF=PASS (`.oracle/evidence/e2e-persistence-proof.txt`):
  same sandbox, second guard evaluation reads omp's own stores via the real
  `detect.scan_providers()` → `['deepseek:ready', 'grok:ready']`,
  `offer_shown=False prompts_printed=[]`. The ready state comes solely from what
  launch #1 persisted (`models.yml` + provenance JSONL) — no env vars involved.
- Also asserted at unit level by merge-idempotence tests in `test_onboarding_wire.py`
  (included in battery a).

### D3. All targeted tests pass; full affected test subset green
- **Battery (a)** `uv run pytest tests/agentbox -q -k onboarding` → **122 passed, 1 skipped** (skip = network-gated verify test behind `RUN_OMP_VERIFY=1`), exit 0.
- **Battery (b)** `uv run pytest tests/test_pipeline_run_cli.py tests/characterization tests/agentbox/test_arnold_agent.py tests/agentbox/test_credentials.py -q` → **137 passed in 254.48s**, exit 0.

### D4. Every agent-goal criterion mapped to evidence; North Star disposition recorded
- This matrix; North Star table below. Docs deliverable: `docs/onboarding.md`
  (+ README pointer after the Quick-start setup paragraph).

## North Star principles

| Principle | Disposition | Evidence |
|---|---|---|
| **Detect before asking.** Found-first ordering beats blank menus | PASS | S1 menu buckets ready→found→missing with origin descriptors and `<- recommended` marker (`flow._render_menu`); parity-tested catalog vs worker tables (`test_onboarding_detect.py::…parity…`, battery a); OpenRouter always reachable via `o`. |
| **One verified route is success.** Optimize time-to-first-working-model | PASS | Flow exits 0 only after ≥1 verified route; loop-back on failed verify, never half-wired (`_configure_provider`, max 3 attempts); E2E launch #1 verified one route then offered exit (`e2e-transcript-launch1.txt`). |
| **Persist once, reuse forever.** No re-prompts | PASS | Persistence proof above (D2). Static keys copied into omp stores (`auth-broker import` / models.yml apiKey); no env-var-only option. |
| **Provenance everywhere.** Failures can name their origin | PASS | Secret-free JSONL ledger `<agent-dir>/…/.arnold_onboarding_provenance.jsonl` written on every verified wiring (`wire.record_provenance`); E2E confirms ledger exists and contains no key material (`e2e-secret-scan.txt`: `scan(fake_key in provenance)=False`). Detection origins recorded per provider (cli_store/env/db/config). |
| **Headless stays fail-closed.** Non-TTY behaves exactly as today | PASS | `guards.should_offer` excludes non-TTY/CI/resume/session-dir/message/stock-omp/resident; golden-file non-TTY stderr byte-identity + preflight exit-7 preservation tests green (`test_onboarding_triggers.py`, battery a); regression subset (battery b, incl. `test_credentials.py`) green. |

## Anti-pattern guards (spot checks)

- Blank-menu wizard: prevented by found-first bucketed menu (see Detect row).
- Copying rotating tokens as static: grok wired via command-backed `apiKey` referencing live token helper copied into agent dir (`wire_cli_proxy`; `grok-token.py` uses runtime `expanduser`).
- Silent import / secret printing: consent prompt before every offer; [W1/R3] scan of full captured transcript → fake key and any `sk-[A-Za-z0-9]{8,}` pattern **absent** (independent grep: 0 matches each). Key persists ONLY in omp's own store (`<agent-dir>/models.yml`) by design.
- Fork changes: none — `git log` shows all four batches touch Arnold-side files only.
- Half-wired exit: exit contract 0/1/2 enforced by unit tests.
- Regressing typed failures: golden-file byte-identity tests + battery (b).

## Verbatim command results

```
$ uv run pytest tests/agentbox -q -k onboarding
122 passed, 1 skipped, 318 deselected in 228.93s (0:03:48)

$ uv run pytest tests/test_pipeline_run_cli.py tests/characterization \
    tests/agentbox/test_arnold_agent.py tests/agentbox/test_credentials.py -q
137 passed in 254.48s

$ uv run python .oracle/evidence/run_e2e_onboarding.py   # batteries c+d+e
W1R3_SECRET_SCAN=PASS
W1R4_HOME_EXPANSION=PASS
PERSISTENCE_PROOF=PASS
```

Full verbatim output for each: files listed in the evidence index.

## Final rework addendum (final-attempt-1 -> GateFR PASS)
- Redaction shapes + secrets threading: tests/agentbox/test_onboarding_wire.py::test_redact_covers_real_key_shapes et al.
- Preflight option [4] store-based readiness: test_onboarding_triggers.py::test_t2_tty_option_4_continues_when_slots_ready_after_flow (+partial-readiness exit-7)
- models.yml flock contention: test_merge_waits_for_external_flock_holder, test_concurrent_merges_keep_every_provider_block
- -r alias guard: guards parametrize extended
- omp_bin dead param removed; no stale callers (grep)
- Accepted P3: over-redaction of hyphenated words in failure output — safe-direction tradeoff.
