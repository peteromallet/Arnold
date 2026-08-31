# Batch-2 attempt-4 post-custody authority review receipt

## Session and boundary proof

- Reviewer model: `openai-codex/gpt-5.6-luna` (current fresh GPT-5.6 Luna/high session).
- Review type: independent source-based authority/checker/integration review.
- No model or reviewer subprocess was launched. No delegation, nesting, Megaplan/Megado invocation, test suite, Batch 3 action, commit, stage, push, merge, reset, source/test mutation, frozen-file mutation, status/history/custody mutation, or index mutation occurred.
- Review cwd: `/Users/peteromalley/Documents/Arnold-oracle-nbf-gate4`.
- Review evidence root: `.oracle/evidence/batch-2-attempt-4-post-custody-authority/`.
- Every command capture has separate `<name>.stdout`, `<name>.stderr`, and `<name>.json` files. Each JSON records literal `argv` (including complete Python `-c` body where used), cwd, UTC start/end, exit, byte counts, and SHA-256 values. The raw capture manifest is `manifest.sha256`.

## Bound identities and rehashes

| Binding | Expected | Observed / status |
|---|---|---|
| branch | `reconcile/nbf-attempt4-2297` | exact |
| HEAD | `2297fb330cdb375b4e5bd048f0d5c37d0e06db30` | exact |
| source/base | `origin/main@798c50619204010ed3f4297fbb57988fe9381924` | exact |
| candidate implementation | `5da26ec5be4d13559948fe4256a114ad7626482b` | `git cat-file -t` returned `commit` |
| full candidate diff | 153829 bytes; `67ddac58cab14775fc375504d340b9afe5c41fb7ae612c10df32fd31482d3163` | exact |
| production candidate diff | 109379 bytes; `009aeb36e1ba2d2812e8c89a792845333acc90ede57b9361e4e79bda9db67d32` | exact |
| packet | `888467b711d8c4de2de0ecfedab7245e0bad3af398e45f0c530dfb089749f078` | exact |
| executor brief | `aac0fc784e5ddf938682298309b94ad4d4f2f5356babb4210467cc440f5368d9` | exact |
| executor finding / receipt | `ac65e5d896a7745330e4aaf9594fd074fc7087adbb7b50f4f90e2df978341cda` / `4fe99da6fde53c45e1ffcbbc1cca732f22e1f00c9735c321633b93dce8cb3502` | exact |
| v2 finding / receipt | `dbcd4a264c42b1cdca952dbb58bee5ad7d1ccbbcc89e1b6ec5eb4895a7a054ff` / `130e1e35883b16738718c46e13f6229b23a64184777790e5a755e791916ef831` | exact |
| v3 finding / receipt | `5c87675363343bddbbaf43e5c7520cf3a6012ae65863151dddbdfcf398571b29` / `2e462d5532577fb348443461bf4369cdec512af0b4f535eefdfee73f6b5ace9e` | exact |
| sealed manifest | `5238ec05d2f19e798c0fa3e8dc7fbe75876505393ef61411b22fa82a86211e5b` | exact |
| tasklist | `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589` | exact |
| North Star | `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e` | exact; canonical block byte-identical with final newline |
| base goal | `2299daefc4b48f361baf5dbe3811d935fe25b5a44adc66bb14b2fbff5a158864` | exact |
| base status | `9f4c6a0794a87d18aaac3e49109baa7ed792d86571483913625ebc1507e362af` | exact |
| frozen plan | `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1` | target `.oracle/plan.md` absent; no current-tree rehash possible |
| base custody | `94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0` | exact |
| custody receipt | `a0ecba2b2c7076bb992fe8169698e895d3e83a49733d0d74c8331dbd1e7dddae` | exact |
| review-policy receipt | `1e22ec54c1c1afb33e3d1faf81d2e49b8b540f6f62dbd7e0b264249716c4bccc` | exact |

The historical `git show 796961cd9c98d7a8b6e800a44a71b7f9bceb54f0:.oracle/plan.md` capture is retained only as proof that a historical object exists; its bytes are not substituted for the absent target file.

## Pre-review repository and index identity

- `git status --porcelain=v1`: exit `0`; stdout 3167 bytes, SHA-256 `77798a8ad849cbe4e2ee2b82e9ab656b40e8e786a4b0962cfb1c1606359ac57f`; stderr 0 bytes, SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
- `git diff --cached --quiet`: exit `0`; stdout/stderr both 0 bytes with empty-stream SHA `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
- `git diff --cached --name-status`: exit `0`; stdout/stderr both 0 bytes with empty-stream SHA.
- Source/test scoped status: exit `0`; stdout 1063 bytes, SHA-256 `6d60afdf6188f124a9093a81b4d37ca0ff8972e590654f10d06d41bc2d4cf3b6`; no untracked source/test paths were present.
- `git diff --check 5da26ec5be4d13559948fe4256a114ad7626482b -- arnold_pipelines scripts tests`: exit `0`; both streams empty.

## Targeted probe evidence

- `scripts/check_worker_admission_authority.py --check`: exit `0`; stdout 213 bytes, SHA-256 `e56d8b9a518cefd21a0aa7da98ed2d0c78b9f0e3a3ce3fcdb4b63f4fa5ae48f2`; stderr empty. This is only the repository scan result, not proof of adversarial completeness.
- Native unknown-model probe: exit `0`; stdout 368 bytes, SHA-256 `e7391eec551a42d980cdca2a7caeb125d2caa5d616da7ae5aa5c092182e8fa6f`; both unknown models returned accepted native proof with `constructable=true`.
- Lifecycle accepted-first probe: exit `0`; stdout 67 bytes, SHA-256 `9921deaaea2929c1f206335eeca4e642a9a42e692f8758e20c3e970c88051196`; first accepted marker was persisted successfully.
- Conflicting terminal payload probe: exit `0`; stdout 69 bytes, SHA-256 `6b6164b6d7a2da3938417e4cdc8adfc9bd41f72ac12abc873228ca1bae2e2302`; changed success payload was not rejected and returned the same terminal event.
- DispatchOutcome identity-field probe: exit `0`; stdout 1141 bytes, SHA-256 `6969598133a5da06bc62937e4e0d576ebf03c765b74a84ab81fcae5257d2b756`; `provider` and `route_liveness_identity` are absent from serialized outcome fields.
- Checker falsey/scope probe: exit `0`; stdout 393 bytes, SHA-256 `1172865345642a3b8cddf99addf1e7540ae1d12b3cc8f7c9193f4e5ba5fbc59c`; `is False` and reversed `False is` forms produced only raw-launch diagnostics, while the configured-mode helper process visitor produced no diagnostic.
- All targeted probes used temporary directories under `/tmp`; no repository file was mutated.

## Fresh capture inventory and hash

The evidence root was assembled from 129 regular files excluding `manifest.sha256`, with canonical lines `<sha256><two spaces><relative POSIX path><newline>` sorted bytewise by relative path. Manifest bytes: 11560. Manifest SHA-256: `18cdf05cc12ec34fce70074d0f931fdcb0ff15fb50b176c252308c4817e69028`. Final newline: present.

## Post-review identity

The check-in and this receipt were written only after source inspection and probes. Post-write identity captures were then taken without touching source, frozen inputs, status/history/custody, or the index. The final post-write porcelain snapshot was taken last among those captures.

- `git branch --show-current`: exit `0`; stdout 28 bytes, SHA-256 `81e2a0353ce3137a02a322adf62dc27ee549004137d8e7a1780265ab066eda65`; exact branch unchanged.
- `git rev-parse HEAD`: exit `0`; stdout 41 bytes, SHA-256 `ea3a3bb36ec3ae1a30dd542056944359cdc5c18f208eb7c352b9c8190cdaa056`; exact HEAD unchanged.
- `git rev-parse origin/main`: exit `0`; stdout 41 bytes, SHA-256 `9fedff586a6415779c6e0e9f8cbad5fd4e0c2e0b5e91379e5a28ec22753a1430`; exact source/base unchanged.
- `git diff --cached --quiet`: exit `0`; stdout/stderr both 0 bytes with empty-stream SHA; no staged paths.
- `git diff --cached --name-status`: exit `0`; stdout/stderr both 0 bytes with empty-stream SHA.
- Final `git status --porcelain=v1`: exit `0`; stdout 3497 bytes, SHA-256 `3210c691017184b60a85e1b0e5f2774cd4c11ad23506cb2d1498ecabd7760394`; stderr 0 bytes with empty-stream SHA. The only status changes attributable to this review are the two requested paths and the fresh evidence-root captures.

- Post-write status capture: `.oracle/evidence/batch-2-attempt-4-post-custody-authority/status-post.stdout` plus its JSON metadata.

## Review findings bound by this receipt

The paired check-in records the source citations and conclusions for all four roots. The material findings are: metadata/callable native proof admits unknown models; typed terminal transport omits route/provider identity and accepts unequal replay payloads; managed launch lacks the WBC closure; accepted-first (and conditionally closed-first) persisted history remains legal; and checker scope/falsey-form coverage is incomplete. These are source/probe findings only; this receipt issues no batch verdict.

## Exact command record location

The literal command records, including full Python bodies, are the per-command JSON files in the evidence root. The raw stdout and stderr streams are adjacent files with the paths and digests recorded by each JSON. This receipt intentionally does not duplicate long Python bodies; it binds the files containing them through the manifest above.
