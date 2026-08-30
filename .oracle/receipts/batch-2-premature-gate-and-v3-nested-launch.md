# Batch-2 orchestration incident receipt — premature gate and nested v3 launch

Append-only orchestration evidence. This is neither executor evidence nor an
Oracle/reviewer verdict. It records two invalid concurrent model branches and
their quarantine disposition; it does not alter or validate their conclusions.

## Immutable run bindings

- Repository: `/Users/peteromalley/Documents/Arnold-oracle-nbf`
- Candidate HEAD: `19deab5bb407273e7e82d40a66fc06d17af93ad4`
- Source/base: `origin/main@798c50619204010ed3f4297fbb57988fe9381924`
- Frozen tasklist SHA-256: `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589`
- North Star SHA-256: `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`
- Correct v3 execution brief: `.oracle/briefs/execution-nbf02-nbf03-luna-v3.md`, SHA-256 `06894b3b35cbd3f47253251ee1e72363c4b96419c2d999bf81c5e2cc97c11156`

## Incident A — premature Sol/Luna gate

The gate began while the valid v3 executor was still editing and before its
finding and receipt existed. It therefore reviewed a mutable, incomplete
candidate and cannot count as the one fresh Batch-2 review.

- Sol fallback input brief: `.oracle/briefs/oracle-nbf02-nbf03-sol-fallback-v2.md`, SHA-256 `d4db9d5581c4b9a1c0401b42f6f26e8236d365c0339c759158399d3befb73b1e`.
- Sol process group `76648`: PID `76648` (`codex exec`, model `gpt-5.6-sol`, reasoning `high`) and PID `76649` (vendor Codex child); observed start `2026-08-30T07:36:19Z` / `07:36:20Z`.
- Delegated Luna review brief: `/tmp/oracle-nbf02-nbf03-luna-review-v2.md`, 4,514 bytes, mtime `2026-08-30T07:39:06Z`, SHA-256 `c1d1da8214c42c695c0ad697101e681063b842e0a7794b8b8fd0e116716e8ebb`.
- Luna reviewer process group `79793`: launcher PID `79793`, OMP PID `79824`, `node_repl` PID `79837`, and `ruff server` PID `82958`; observed start `2026-08-30T07:39:19Z`. The launcher selected `codex:gpt-5.6-luna` without an explicit `:high`; the OMP argv had no `--thinking high` flag even though the review prompt requested high reasoning.
- Premature temporary evidence root: `/private/tmp/oracle-nbf02-nbf03-luna-review-0830/` (24 files). `manifest.json` was 7,133 bytes, mtime `2026-08-30T07:50:05Z`, SHA-256 `fa06fb62b38642863df9d9b080c953ca92e6538d8c31809dd81af6bad3082176`. The SHA-256 of the lexically sorted `shasum -a 256` inventory for all 24 files was `34ffd105a02a78e66659c8a2b22461cce2f22af2991e4bfcb718c4e5af3acd97`.
- `/tmp/oracle-nbf02-nbf03-sol-fallback-v2-luna.meta.json` was not created.

At `2026-08-30T07:50:39Z`, argv and process groups were reverified. `SIGTERM`
was sent first to process groups `-79793` and `-76648`. All six listed
processes exited within the bounded three-second poll; no `SIGKILL` was needed.
The valid v3 executor group `80650` (launcher `80650`, OMP `80680`, tool runner
`82293`) remained alive and was not signalled.

None of the four expected repository gate artifacts existed at termination and
none existed at the evidence-seal audit:

- `.oracle/checkins/batch-2-luna.md`
- `.oracle/receipts/oracle-nbf02-nbf03-luna.md`
- `.oracle/checkins/batch-2-sol-fallback-v2.md`
- `.oracle/receipts/oracle-nbf02-nbf03-sol-fallback-v2.md`

The temporary review brief/evidence is quarantined by classification only: it
was not deleted or modified, must not be cited as a valid review, and supplies
no Batch-2 verdict.

## Incident B — nested same-model launch inside v3

The v3 evidence root contains a nested same-model launcher transcript even
though the v3 brief prohibited a nested harness:

- Root: `/private/tmp/oracle-nbf02-nbf03-luna-v3-0830/launcher/`
- `stderr.txt`: 417 bytes; SHA-256 `85698e77f9b1432affc7506c45d7f5038e80f284ae42d37c083ccef694770d59`; it resolves `codex:gpt-5.6-luna:high` to `openai-codex/gpt-5.6-luna`, records `thinking=high` and the repository CWD, then ends at `Working...`.
- `stdout.txt`: 0 bytes; SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
- `end.txt`: `2026-08-30T07:44:31.624259000Z`; SHA-256 `ed56b327478d646d39e85e3264ab275c0ca7013d1df82515923d13f64aeaf33b`.
- `exit.txt`: `143`; SHA-256 `9d9b18720961e9b4689fd763b85e7b6f36160ccd3a8a1c9ddc5103bb0f66c396`.
- No final model output was captured.

This transcript is not the top-level v3 executor stream and must not be used as
its completion status. The nested launch produced no valid executor finding or
receipt of its own and does not count as an executor or review pass. The valid
top-level v3 route is instead proven by the independently observed process argv:
launcher PID `80650` selected `--model=codex:gpt-5.6-luna:high` and
`--timeout=3600`; child PID `80680` resolved to
`openai-codex/gpt-5.6-luna --thinking high`.

## Disposition

- Premature gate: terminated and quarantined; no repository verdict.
- Nested v3 launch: terminated with status `143`; no final output; invalid as
  separate executor evidence.
- Valid v3 implementation/test transcripts remain executor evidence only and
  still require a fresh post-completion review before any Batch-2 verdict.
- No source, test, history, frozen planning, status, goal, custody, stage,
  commit, push, merge, live-box, chain, or Batch-3 mutation was performed by
  this incident receipt.
