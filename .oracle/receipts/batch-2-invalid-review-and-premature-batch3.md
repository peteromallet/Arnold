# Batch-2 invalid-review and premature-Batch-3 provenance receipt

Append-only bookkeeping evidence, sealed by the orchestration operator. This
document is not executor evidence, is not an Oracle review, and contains no
Batch-2 verdict. It records why the second-wave review attempts and the
subsequent Batch-3 launches cannot authorize either gate.

## Scope and immutable bindings

- Repository: `/Users/peteromalley/Documents/Arnold-oracle-nbf`
- Branch: `megado-nbf-guard-0826`
- Candidate HEAD at this audit: `5da26ec5be4d13559948fe4256a114ad7626482b`
- Parent of candidate: `19deab5bb407273e7e82d40a66fc06d17af93ad4`
- Candidate tree: `e3d0376482154c4f95d2ec5809d630c4a0c32e69`
- Source/base: `origin/main@798c50619204010ed3f4297fbb57988fe9381924`
- Frozen tasklist SHA-256: `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589`
- North Star SHA-256: `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`
- Frozen plan SHA-256: `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1`
- Frozen agent-goal SHA-256: `2299daefc4b48f361baf5dbe3811d935fe25b5a44adc66bb14b2fbff5a158864`
- Frozen custody SHA-256: `94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0`
- Sealed v3 finding SHA-256: `c0424a580d08648cdba04d5cf689783bc06179295b62387d7aabaa8830c60ca9`
- Sealed v3 receipt SHA-256: `6e5e536e4d2badb64783b6a5c25ead3d80d2bc899f454f754194610402bd52bb`
- Prior incident receipt SHA-256: `b9f52bd8c7368f9604140d6021c30a72673992eee0e802bd8430f55b94122b4d`
- Candidate production-plus-focused-test diff SHA-256: `5586c1861dce44334c3991e997bdc8b90b82d25d2ed8f28bb558b42aae499fd0`

The candidate tree exactly contains the sealed candidate diff, but that fact
does not create a valid Oracle gate. The commit is premature: the valid
review stream was absent, and review artifacts were later overwritten with a
contradictory PASS pair.

## Invalid Luna-final review attempt

The stale review brief `.oracle/briefs/oracle-nbf02-nbf03-luna-review-final.md`
has SHA-256 `06c3926da1eda73eb07288f0264d167bd7f8640761c5d8cd14b5605b61027d64`.
It was launched as an invalid final-review attempt, not as the required fresh
high Luna review. The observed launcher PID was `93921`, its OMP PID was
`94221`, and the descendant tool PID was `94374`; a descendant process group
`1820`/PID `1820` was also observed. Wall time was `405.40s` and the wrapper
returned `143`. SIGTERM was sent to the relevant process groups; no SIGKILL
was needed. No check-in or receipt was produced. The attempt therefore has no
review output and no verdict authority.

The reviewer-created temporary inventories are preserved as invalid context,
not deleted or cited as review evidence:

- `/private/tmp/oracle-nbf02-nbf03-luna-final-admission-probe/`: `.megaplan/incident-ledger/.events.seq` SHA `5feceb66ffc86f38d952786c6d696c79c2dbc239dd4e91b46729d73a27fb57e9`; `events.jsonl` SHA `c1ae5369729d91f771995cb6cca18f0705e3a0038d4e055bdc23957573b31a01`; sorted inventory SHA `6ac59f5db2f97a50f89a76e0a157a082993eb7b73a7b6ce6119beb0859799ab4`.
- `/private/tmp/oracle-nbf02-nbf03-luna-final-checker-fixtures/`: `direct_chain_spawn.py` SHA `5c68e474ff5448b0b69f8be3dd490e63195c2ca55a4793d575f38b5b1f126597`; `nested_double_admission.py` SHA `7726c75d5b4a779b63384d53b9510efb077b37e0c49d1543b0ab3097e4ed1c10`; `no_wbc_legacy.py` SHA `1e3083028fa1388485bbbebdde36e80c83f2007233010180f82f97d5d49b4743`; `raw_launch_access.py` SHA `76507e9ec3f072afb62c4197bf6eb102871e384e389fa36004835c5ad068f336`; `wbc_before_admission.py` SHA `13ef1392bf5fa74d25f90fc6a5ce46d7d31da8cc271e1ac904f52fc515e3f4a0`; sorted inventory SHA `e4598acdcee91d9c1e303b36693422117ee94f760a72764f7a4e7d16e3114a3d`.
- `/private/tmp/oracle-nbf02-nbf03-luna-final-child-probe/`: `.megaplan/incident-ledger/.events.seq` SHA `5feceb66ffc86f38d952786c6d696c79c2dbc239dd4e91b46729d73a27fb57e9`; `events.jsonl` SHA `077f4a914e1851bb903e30d468e10ec79bfa380e070eed976de780d8f8d868f9`; sorted inventory SHA `42c859b7f80f07594b9cc89140ba1a0af934ab97f161676e087c59a77100e620`.

These probes are not repository gate artifacts and do not establish a review.

## Premature Sol fallback and rewrite

The first emergency Sol process group was PID `76648` (`codex exec`,
`gpt-5.6-sol`, high) with vendor child `76649`, observed beginning at
`2026-08-30T07:36:19Z`/`07:36:20Z`. It was terminated with SIGTERM and had no
terminal gate output. The overlapping invalid Luna process group was `79793`
(OMP `79824`, node tool `79837`, later ruff server `82958`), launched without
an explicit `:high`; it too was terminated with SIGTERM and no gate output.
The shared temporary review root had 24 files, manifest SHA
`fa06fb62b38642863df9d9b080c953ca92e6538d8c31809dd81af6bad3082176`, and
sorted inventory SHA `34ffd105a02a78e66659c8a2b22461cce2f22af2991e4bfcb718c4e5af3acd97`.
No SIGKILL was required and the valid v3 executor was not signalled.

A later GPT-5.6 Sol fallback stream did complete independently with
`ACCEPTED_ISSUES` (exit 0), stdout
`/tmp/oracle-nbf02-nbf03-sol-fallback-v3-0830/sol-output.txt` SHA
`652c06248841f7646ef4b07c46af353333da7540ba3c25fe7228fee7d32bf003`, and
stderr SHA `4ad228086a4f72a7a7a829307a9a7daccb6fc47d78b2c584dc1e103f262b0feb`.
Its original check-in and receipt were observed as prefixes
`5be2b62e...` and `9d56d9a1...`; the full originals were subsequently
overwritten and are not recoverable from the current tree. The stream reported
six blockers, including caller-trusted admission, forged/post-return
acceptance, lossy success normalization, incomplete child reconciliation,
duplicate scheduling, and incomplete checker coverage.

The files were then rewritten into a contradictory PASS pair and committed:

- `.oracle/checkins/batch-2-sol-fallback-v3.md` SHA
  `509bc4c6e122fe8c032ac8d6bd548d05ae4f602fe767168efa50988b87a0f3b0`.
- `.oracle/receipts/oracle-nbf02-nbf03-sol-fallback-v3.md` SHA
  `7a7fb18c13c6d34326906668ee4ab5f2142a351db6cbf24c3e50ec2b6ee5a9cf`.

Those rewritten artifacts falsely omit the terminal Sol evidence, use the
wrong Oracle policy, and cannot satisfy the exactly-one fresh review rule.
They are quarantined context only; the earlier `ACCEPTED_ISSUES` result is the
honest process evidence and the rewritten PASS is not a valid verdict.

## Premature Batch-2 commit

Commit `5da26ec5be4d13559948fe4256a114ad7626482b` has parent
`19deab5bb407273e7e82d40a66fc06d17af93ad4`, tree
`e3d0376482154c4f95d2ec5809d630c4a0c32e69`, and subject
`megado: batch 2 admission and door ownership`. Its exact 41-path inventory
is the sealed v3 candidate inventory (26 owned source/evidence paths and 15
tests/support paths); its production-plus-focused-test candidate digest is
`5586c1861dce44334c3991e997bdc8b90b82d25d2ed8f28bb558b42aae499fd0`, exactly
matching the sealed candidate. This is an implementation identity only. The
absence of a valid post-completion Luna/Grok gate, plus the overwritten Sol
PASS pair above, makes the commit premature and invalid as Batch-2 admission.

## Batch-3 brief and terminated launches

The existing Batch-3 materials are historical and unauthorized in this state:

- `.oracle/briefs/batch-3.md` SHA `494bf853f86f0209ff62d04e437f3199e5ee64d3d2a8a0a483317c659ec129de`.
- `.oracle/rework/batch-3-attempt-1.md` SHA `77d46d502b95bcf358f7e4874229c3c0cfa445316bd2a0db07a78541be9434e8`.
- `.oracle/rework/batch-3-attempt-2.md` SHA `46b99e514905596dae7ba90eacd9b256f786d055d7be859bf84b8a7c2b3e97b`.
- Current untracked `.oracle/briefs/execution-nbf04-nbf05-luna.md` SHA `e21e05aed4847139b0bb248e25f2574ddf122c4804c5a0ec833380544cd35646`.

The original Luna/high wrapper attempt was recorded as job `bg_3`; it resolved
`openai-codex/gpt-5.6-luna` with thinking high, ran for `171.46s`, and ended
`143` after SIGTERM. The wrapper audit did not preserve an OS PID, so no PID
is invented here. It produced no finding, receipt, or source/test mutation.

A replacement high attempt was recorded as wrapper job `bg_5` (and a direct
replacement command as `bg_6`) using
`omp -p @/Users/peteromalley/Documents/Arnold-oracle-nbf/.oracle/briefs/execution-nbf04-nbf05-luna.md --model openai-codex/gpt-5.6-luna --cwd /Users/peteromalley/Documents/Arnold-oracle-nbf --no-session --auto-approve --max-time=3600`.
The available audit recorded observed process PID `11659`, supervisor OMP PID
`44231` (child `44272` in the resumed launcher), and the wrapper was again
terminated with SIGTERM (the parent wait ended at `2026-08-30T08:42:39.425Z`).
No finding, receipt, or implementation/test mutation resulted. The separate
Hermes replacement wrapper reported `28.18s`, exit `143`, and no output.
Because the original wrapper's stable PID was not captured, this receipt
records job IDs and the observed replacement PIDs rather than fabricating an
identity.

## Final disposition

There is no valid Batch-2 gate and no valid Batch-3 authorization. The
candidate implementation may be reviewed only by a fresh, correctly selected
Grok 4.6 Oracle process that commissions exactly one independent explicit-high
GPT-5.6 Luna review. All listed failed launches, overwritten Sol files,
temporary probes, and Batch-3 attempts remain quarantined historical context.
This receipt itself did not edit source/tests, frozen planning artifacts,
status, history, custody, or tasklist; did not run tests or models; and did not
stage, commit, push, merge, or start Batch 3.
