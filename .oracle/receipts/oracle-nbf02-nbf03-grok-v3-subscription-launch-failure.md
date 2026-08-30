# Batch-2 direct Grok v3 subscription launch-failure receipt

This is append-only executor/orchestration evidence, not an Oracle review or
verdict. It records the authorized direct-subscription launch failure and the
resulting stop condition. No reviewer was commissioned and no gate artifact
was produced.

## Immutable bindings

- Repository: `/Users/peteromalley/Documents/Arnold-oracle-nbf`
- Branch: `megado-nbf-guard-0826`
- Observed HEAD: `5f172e3588e740bacd6692ca9e4cc50ae01f6a6b`
- Candidate implementation parent: `5da26ec5be4d13559948fe4256a114ad7626482b`
- Candidate tree: `e3d0376482154c4f95d2ec5809d630c4a0c32e69`
- Candidate sealed production-plus-focused-test digest: `5586c1861dce44334c3991e997bdc8b90b82d25d2ed8f28bb558b42aae499fdc0`
- Source/base: `origin/main@798c50619204010ed3f4297fbb57988fe9381924`
- Direct v3 gate brief: `.oracle/briefs/oracle-nbf02-nbf03-grok-v3.md`
- Direct v3 gate brief SHA-256: `0f5dd6b85165c2be927f1e0843207db791db2721c80af560fc618ff8015163f3`
- Frozen tasklist SHA-256: `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589`
- North Star SHA-256: `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`
- Frozen plan SHA-256: `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1`
- Frozen agent-goal SHA-256: `2299daefc4b48f361baf5dbe3811d935fe25b5a44adc66bb14b2fbff5a158864`
- Frozen custody SHA-256: `94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0`

## Direct binary, authentication, and entitlement

- Resolved primary binary: `/Users/peteromalley/.grok/bin/grok`
- Alternate installation observed: `/Users/peteromalley/.local/bin/grok`
- Version: `grok 1.0.5 (5115b46bc909)`
- CLI identity: `Grok Build TUI`; the direct native `grok.com` subscription path
  was selected, not OMP/OpenRouter.
- Requested model: `grok-4.6`
- Requested reasoning: `--reasoning-effort high`
- Authentication: native Grok Build account/session selected by the direct
  binary; no credential value is recorded.
- Entitlement result: the provider authenticated the request far enough to
  return the exact Grok Build balance error below; the account had no usable
  Grok Build usage balance for this request.

## Exact invocation and observed result

Exact command:

```text
grok --prompt-file /Users/peteromalley/Documents/Arnold-oracle-nbf/.oracle/briefs/oracle-nbf02-nbf03-grok-v3.md -m grok-4.6 --reasoning-effort high
```

- Working directory: `/Users/peteromalley/Documents/Arnold-oracle-nbf`
- Exit status: `1`
- Provider error (verbatim): `API error (status 402 Payment Required): Grok Build usage balance exhausted`
- Launcher PID, child PIDs, UTC start, UTC end, and duration: **not recoverable
  from the observer export available during this bookkeeping pass**.
- Capture directory: **no persisted direct-v3 capture directory was present in
  the observer/tmp stores inspected during this bookkeeping pass**.
- stdout bytes/SHA-256: **not recoverable; no stream was preserved**.
- stderr bytes/SHA-256: **not recoverable; no stream was preserved**.
- metadata bytes/SHA-256: **not recoverable; no metadata record was preserved**.

The missing observer fields are intentionally marked unavailable; this receipt
does not invent process identifiers, timestamps, byte counts, or digests. The
exact command, binary/version, model/reasoning selection, exit status, and
provider error above are the complete recoverable evidence.

## Boundary and stop disposition

- No Luna reviewer was launched or commissioned by this failed invocation.
- No Grok check-in, Luna check-in, review receipt, or verdict artifact was
  created by this failed invocation.
- No fallback provider, second reviewer, nested harness, source/test edit, or
  worktree mutation occurred.
- The earlier OMP/OpenRouter HTTP 402 is historical routing failure evidence
  only; it is distinct from and does not establish the native subscription
  result recorded here.
- Stop condition: confirmed native Grok Build usage-balance exhaustion. Do not
  fabricate `PASS_BATCH_2` or `ACCEPTED_ISSUES`.
- Next action: retry the exact direct v3 command after the Grok Build balance
  resets, or wait for explicit user authorization to change the Oracle model.

Recorded 2026-08-30 as executor bookkeeping evidence.
