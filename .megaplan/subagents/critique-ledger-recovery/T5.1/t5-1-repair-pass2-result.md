# T5.1 Repair Pass 2 Result

Status: **candidate repair complete; formal T5.1 and all four owner decisions
remain pending**.

## Exact candidate

- Commit: `7c254f7f0d15ba4e835a6fe7cae40b47d29ef7cd`
- Tree: `27e7b22ef0d7f3faeaa6b7cbcd63aabb2872d7e9`
- Exact parent: `c703628d728096573df82b22af9f46c70a7c28d3`
- Parent tree: `5094ab7750aa474cbe1c220d24e18e8aa4a9acfb`
- Branch/worktree: `fix/critique-recovery-t5-1-20260802` at
  `/private/tmp/arnold-critique-recovery-t5-1-20260802`
- Commit subject: `docs(critique-ledger): harden T5.1 evidence verifier`
- Final `git status --porcelain=v1`: empty

Independent code rehashed the raw Git commit and tree objects and reproduced the
exact commit/tree IDs above. The commit is a single clean child of the reviewed
pass-2 input `c703628d…` and changes exactly the seven allowlisted T5.1 paths.

## Repair outcome

The candidate now closes every bypass documented by
`independent-review-pass2.md`:

1. The three nested M6A references are derived in canonical order from the
   exact immutable M6A JSON object. The verifier requires exactly those three
   unique role/path/commit/blob/SHA-256 entries and rejects missing, extra,
   duplicate, reordered, and substituted references.
2. The 13-file blocker-004 list is derived by flattening the exact M6A
   `boundary`, `runtime`, `schema`, and `support` categories. The verifier
   requires the exact ordered set of 13 unique paths, exactly once each, and
   binds every baseline/modified blob and SHA-256 to both Git and M6A.
3. Historical M6A, raw source, recovery base, M5 bound head, WBC baseline,
   modifying commit/tree/parent/subject/path-set/diff, semantic evidence, and
   exact probe identities are closed-world constants checked against available
   immutable Git objects. The unavailable `904560e…` object remains rejected.
4. Active blocker IDs and semantic keys, the non-counting alias, resolved
   historical blockers, owner decisions, guardrails, source refs, successor
   refs, and input contract are content-bound. The jointly forged alias/target
   semantic bypass and forged reviewer ID now reject.
5. The exact AST probe now binds its probe ID, executor, source and constants
   objects, ordered constant-name digest, function, assertion set, expected row
   and mapping counts, empty-mapping digest, and full result digest.
6. The manifest is closed-world over exact repair parent/source/M6A identities,
   changed paths, derived counts, tamper-probe-set digest, and six exact artifact
   hashes. The verifier requires a clean committed child of `c703628d…` and
   checks checkout bytes against `HEAD`.
7. The receipt is parsed as an output claim rather than trusted as authority. It
   is replay-bound to the current verifier SHA-256, ledger/technical digests,
   exact repair parent, exact check set/counts, and exact ordered tamper-probe
   list.
8. The previous nine probes were expanded to 88 deterministic negative probes.
   These cover all pass-2 exploits plus missing/extra/duplicate/reordered refs,
   canonicalization ambiguity, source and historical identity forgery,
   commit/tree/parent/path/blob/digest substitution, probe forgery, manifest
   corruption, and receipt replay.

The corrected pass-1 facts are preserved: five active semantic blocker
categories, one non-counting historical alias, two non-counting technical
resolutions, three exact nested M6A refs, 12/13 matching WBC files with only
`source_compiler.py` changed, and exactly four explicit pending owner decisions.

## Exact hashes

| Artifact | Git blob | SHA-256 |
|---|---|---|
| `.megaplan/subagents/critique-ledger-recovery/T5.1/result.md` | `166dbbee99ee8b8d2c10d091f15978b813a367bd` | `d4f85dba3054d9d366f043093f30bd44019b53ca6155aaf184fdfbc1f1344b14` |
| `evidence/critique-ledger-recovery/T5.1/README.md` | `73469a327c5ae7a85367abcf355bff8b80798797` | `9047adf79915751c546a8b5a153c8dadab56c5901aa64ca3e03e46291e17b851` |
| `evidence/critique-ledger-recovery/T5.1/candidate-manifest.json` | `52c21a05dad0aee7ea41006d749ccd9a95944774` | `a5a340c3bdaeaecf535f009a9fda3ca37017e3cb27c287fcf997dd817d19c256` |
| `evidence/critique-ledger-recovery/T5.1/raw-cl1-blocker-ledger.json` | `d3c3180406706d2b09cf5d599d4438cf4b24c609` | `ab748eb288c2e219815afdda338bd4eed8f6cd71547adb43b393aa6d1f654052` |
| `evidence/critique-ledger-recovery/T5.1/technical-resolution.json` | `b0532d46eb6c00417c30017983fb6fea312d9284` | `36f0d0129d7ddcf02b135fc46747b7cd222664d406ba3699c33a2539d65f6e98` |
| `evidence/critique-ledger-recovery/T5.1/verification-receipt.json` | `f139742513c97a5f9e5e04065b1038e6ac586f96` | `0bce23950be01f7535d4acf2c9cff66b4cf16fb93c571a0217ddbe083e520636` |
| `evidence/critique-ledger-recovery/T5.1/verify_raw_cl1_blockers.py` | `45569e09303cbdddcc38f2ed63ed47929b4e5b8e` | `ed410ade83c36069b17945dd4ea5ff0e0ba9aa8aadbf5258bfdd7de0ebd9d895` |

Tamper probe count: 88. Ordered probe-name set SHA-256:
`1a77bc608c6c6d93f06be74a407025f6297d25bf37d23f8207d97701a9312cbe`.

## Verification performed

The exact clean committed candidate passed:

```sh
python -I evidence/critique-ledger-recovery/T5.1/verify_raw_cl1_blockers.py
ruff check evidence/critique-ledger-recovery/T5.1/verify_raw_cl1_blockers.py
git diff-tree --check 7c254f7f0d15ba4e835a6fe7cae40b47d29ef7cd^
git fsck --no-progress --no-dangling --no-reflogs --unreachable
```

Verifier output bound and reported:

```text
passed=true
candidate_head=7c254f7f0d15ba4e835a6fe7cae40b47d29ef7cd
candidate_tree=27e7b22ef0d7f3faeaa6b7cbcd63aabb2872d7e9
candidate_parent=c703628d728096573df82b22af9f46c70a7c28d3
changed_path_count=7
raw_source_objects=6
successor_evidence_objects=4
active_blockers=5
pending_owner_decisions=4
nested_m6a_refs=3
blocker_003_commit_count=578
wbc_files=13 (12 match, 1 mismatch)
exact_probe_mappings=27
negative_tamper_probes=88
formal_completion=false
t5_2_authorized=false
```

Separate code that did not import or call the supplied verifier independently
rehashed the commit/tree, all six manifest artifacts, the manifest and receipt,
the active blocker and owner-decision facts, the historical M6A object, all
three derived nested refs, and the exact 13-path M6A/WBC equality. Result: PASS.

## Limitations and authority boundary

- This is a repaired candidate evidence/verifier bundle, not an independent
  acceptance review and not an owner receipt.
- The final Git commit and tree cannot be declared inside their own tree without
  an impossible content-address self-reference. The in-tree verifier therefore
  binds the exact parent, clean committed child, changed-path allowlist, and
  checkout-vs-HEAD bytes, then derives and prints the final HEAD/tree. This
  external result pins those emitted IDs; a fresh independent reviewer must pin
  them again.
- The T0.2/T0.4 capture-context SHA-256 identifiers remain historical context
  only; those external artifacts are not members of this candidate commit and
  are not used to derive technical resolution or acceptance.
- All four decisions `T5.1-OWNER-001` through `004` remain
  `OWNER_DECISION_PENDING`, `accepted=false`, `receipt=null`.

No T5.1 completion, CL2 acceptance, T5.2 authorization, v3 identity allocation,
cloud/provider action, owner/Run Authority/Custody/WBC mutation, active-lane
change, checklist edit, launch, publication, or other external effect was
performed or authorized.
