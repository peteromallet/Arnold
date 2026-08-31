# Batch-2 attempt-4 post-exit evidence-gap receipt

Sealed audit time: `2026-08-30T20:59:47Z` onward.

This is an independent evidence-integrity audit, not an implementation record,
review, Oracle judgment, or Batch-2 verdict. The attempt-4 candidate was not
modified. No source, test, frozen document, status, index, history, or prior
artifact was changed while producing this receipt.

## Disposition

The attempt-4 executor evidence is truthful about its observed test results but
is not complete enough for `.oracle/evidence/batch-2-attempt-4-sealed.md`.
Therefore no canonical PASS-capable evidence seal was written.

Three evidence-contract gaps remain:

1. The packet-required literal shell raw-symbol command was not executed or
   captured. The finding and receipt explicitly disclose that a specialized
   repository-search tool was substituted. The external evidence root contains
   no raw-scan JSON/stdout/stderr triplet, so there is no literal argv, cwd,
   UTC timing, exit status, or separate stream identity for this required gate.
2. The packet requires the four NBF-03 babysitter failures to be classified
   with parent **and clean-source-checkpoint reproduction**. Attempt 4 captured
   parent-path equality, three current hashes, and renderer absence, but did not
   capture a fresh isolated clean-source-checkpoint pytest reproduction. The
   versioned artifacts bind the prior attempt-3 seal but do not state a reused
   identical clean-reproduction command/receipt as the attempt-4 packet
   requires. The attempt-4 packet itself does not freeze a literal clean-copy
   construction/pytest argv, so a new execution brief must make that argv and
   isolation procedure explicit.
3. Both executor artifacts claim that the sorted 90-file evidence manifest
   hashes to
   `e1e935082721b2cd157a4ba1948574e5e76e0153f179f27e08cbdff8e55c11c4`,
   but no manifest file or construction algorithm was captured. Recomputing
   the canonical lexical form used by the prior seal—the SHA-256 of sorted
   `shasum -a 256` lines with evidence-root-relative paths—produced
   `a05b77ae34a5464cd161c5763f5b27caa78ec65f196c4939f538837287f8fc86`,
   not the claimed value. The claimed external-root digest is therefore not
   independently reproducible from the preserved 90 files.

## Exact missing raw-symbol command

The exact packet command that requires a fresh literal shell capture is:

```bash
if rg -n \
  'refresh_runtime_launch_seed_for_worker_dispatch|require_configured_runtime_launch' \
  arnold_pipelines/megaplan/workers/_impl.py \
  arnold_pipelines/megaplan/workers/omp.py \
  arnold_pipelines/megaplan/cloud/babysitter/launch.py
then
  exit 1
fi
```

Required evidence: literal shell argv/command text, repository cwd, UTC
start/end, exit `0`, empty stdout and stderr with SHA-256
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`,
pre/post porcelain, and changed-path hashes.

## Clean-baseline proof contract

The packet does not supply an exact literal isolated-copy command. It requires
a fresh clean source-checkpoint reproduction of the two babysitter modules,
with complete isolation construction and pytest argv captured, that exits `1`
with exactly `12 passed, 4 failed` and the same four test identities:

1. `tests/cloud/test_babysitter_routing.py::test_babysitter_routing_defaults_to_legacy_deepseek`
2. `tests/cloud/test_babysitter_routing.py::test_legacy_managed_spec_keeps_hermes_controller`
3. `tests/cloud/test_babysitter_goal.py::test_renderer_requires_single_flash_orchestrator_contract`
4. `tests/cloud/test_babysitter_goal.py::test_renderer_cli_mentions_single_flash_contract`

The historical accepted clean reproduction has stdout SHA-256
`f95a7400938f47c4a8e82b2636fc6f345ba7548a8ecd4bb7f9ec0f677b29f12c`.
The reproduction must be paired with the packet's exact parent-preservation
proof:

```bash
git diff --quiet 19deab5bb407273e7e82d40a66fc06d17af93ad4 -- \
  arnold_pipelines/megaplan/cloud/babysitter/routing.py \
  skills/babysitter/scripts/render_babysitter_goal.py \
  tests/cloud/test_babysitter_routing.py \
  tests/cloud/test_babysitter_goal.py
shasum -a 256 \
  arnold_pipelines/megaplan/cloud/babysitter/routing.py \
  tests/cloud/test_babysitter_routing.py \
  tests/cloud/test_babysitter_goal.py
test -z "$(git ls-tree -r --name-only 19deab5bb407273e7e82d40a66fc06d17af93ad4 -- skills/babysitter/scripts/render_babysitter_goal.py)"
test -z "$(git ls-tree -r --name-only HEAD -- skills/babysitter/scripts/render_babysitter_goal.py)"
```

Attempt 4 captured these four parent-preservation commands successfully, but
not the fresh isolated pytest reproduction.

## Verified evidence that remains usable

- Wrapper/launcher/model interval:
  `2026-08-30T20:28:46.225811000Z` to
  `2026-08-30T20:58:58.224344000Z`; launcher PID `87452`; exit `0`.
  Wrapper meta/stdout/stderr SHA-256:
  `60bbe0e2442238db58819c9ffdcd69c1708488abebc6384c1120639a9cf2235d`,
  `3305f093810a7ad0d686178e98ded3f5d80878c1da5dc11c9c91f696ae3271a0`,
  `3bae769be3ce31ff2eba509988b31942827e05a5a1b6aa70f0aea730725033da`.
  No attempt-4 launcher/model process remained and no nested AI model was
  observed after exit.
- Finding SHA-256:
  `ac65e5d896a7745330e4aaf9594fd074fc7087adbb7b50f4f90e2df978341cda`.
- Executor receipt SHA-256:
  `4fe99da6fde53c45e1ffcbbc1cca732f22e1f00c9735c321633b93dce8cb3502`.
- All 30 JSON command records parsed and had the required structured fields.
  Every paired stdout/stderr byte count and SHA-256 matched; mismatch count
  was zero. Focused roots passed `4/5/5/5`; authority passed `14`; preserved
  suites passed `59/53/90/74`; initial frozen NBF-02 preserved
  `254 passed, 3 failed`; corrected identical rerun passed `257`; frozen
  NBF-03 recorded `60 passed, 4 failed`; checker, compile, and diff-check exited
  `0`.
- HEAD: `2297fb330cdb375b4e5bd048f0d5c37d0e06db30`; branch:
  `megado-nbf-guard-0826`; `origin/main`:
  `798c50619204010ed3f4297fbb57988fe9381924`; index empty/clean.
- Final source/test diff: `153829` bytes, SHA-256
  `67ddac58cab14775fc375504d340b9afe5c41fb7ae612c10df32fd31482d3163`;
  21 modified tracked paths, `1892` insertions, `86` deletions, and no
  untracked path under `arnold_pipelines`, `scripts`, or `tests`.
- Production diff: `109379` bytes, SHA-256
  `009aeb36e1ba2d2812e8c89a792845333acc90ede57b9361e4e79bda9db67d32`.
- Frozen hashes remained unchanged: tasklist
  `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589`;
  North Star
  `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`;
  plan `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1`;
  goal `2299daefc4b48f361baf5dbe3811d935fe25b5a44adc66bb14b2fbff5a158864`;
  custody `94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0`.

## Closure condition

A narrowly scoped Luna evidence-correction pass may close this receipt without
changing implementation: run and capture the exact literal shell raw scan;
run and capture an explicitly frozen isolated clean-source-checkpoint pytest
reproduction; generate and preserve a canonical relative-path evidence
manifest with its construction defined. Then issue new versioned corrected
executor evidence and a new independent seal. Do not rewrite this receipt or
the attempt-4 executor artifacts.
