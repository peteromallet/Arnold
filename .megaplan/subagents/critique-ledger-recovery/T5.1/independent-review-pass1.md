# T5.1 Independent Review — Pass 1

## Overall verdict: FAIL

The candidate bundle is fail-closed and its declared hashes/structure reproduce,
but it does not satisfy the evidence-only acceptance contract. It preserves a
cross-category duplicate blocker, and the claimed immutable source for the
003/004 technical resolution is not independently bound to an available exact
Git head.

Reviewed commit: `e72d2baf892613cad391df1a86e4d04b3ff29547`.

Review worktree: `/private/tmp/arnold-critique-recovery-t5-1-20260802`.
`HEAD` equals the required commit; `git status --porcelain`, unstaged diff,
and staged diff were empty. Commit tree: `e7c90cc1c0a5726c72f0243c4729042aebf24b44`.
The master checklist was read from
`/Users/peteromalley/Documents/Arnold/docs/arnold/critique-ledger-incident-prevention-and-durable-recovery-plan-2026-08-02.md`
(SHA-256 `fa174f33bc98b68504d8a2813a645e399015421c542ec9d43c374671dc11afb8`),
including T0.2 and T5.1–T5.6. T5.1 remains marked `Evidence: _pending_`.

Candidate manifest SHA-256, independently computed:
`a9e28d77eb14abaf9d66bac626db8b5453195bd688305a9e3b9bf0061a89b423`.

## Ranked findings

| Rank | Proposition | Verdict | Exact evidence / independent result | Consequence |
|---|---|---|---|---|
| 1 | No blocker is duplicated. | **FAIL** | Immutable source `23ed58c1074dbd78d75e0bc8008376426225de51:evidence/ownership-decision-record.json` (blob `9ab3165d4623c1602b9ed6956b1ffc45a2889797`, SHA-256 `aae3dc0b7f404b5cb3ce749f5407c43b92b608f71ea7675ecc624e7aa3d266a4`) contains `OWNERSHIP-BLOCKER-002` for the portfolio PC decision. The same source commit’s `evidence/pc-scope-decision.json` (blob `cbcba12e93893f62133ed9138b118394460f865d`, SHA-256 `0bbd9ca61699ce6b0f19b812e0656d957a0f5589148109b3ace8f637f9754e0d`) contains `PC-SCOPE-BLOCKER-001` for that same decision. The candidate explicitly repeats the duplicate at `evidence/critique-ledger-recovery/T5.1/raw-cl1-blocker-ledger.json:160-162`. Independent probe printed both descriptions and `CROSS_CATEGORY_DUPLICATE True`. | The five category labels are unique, but the active blocker inventory is not. The supplied verifier checks only category strings and misses this material false condition. |
| 2 | Resolution of blocker 003 is supported by exact immutable source. | **FAIL** | Candidate ledger `raw-cl1-blocker-ledger.json:165-167` relies on `evidence/m6a-prerequisite-resolution.json` at commit `6787d6363e8fc0603092913ae877db14f3b9fff8`, blob `3348f4dbdb9c670d07a41c94fe92bf54f0085569`, SHA-256 `c69783608f3202490b2326c042f3c8457a0034ba6db41ee4fbb910f69c137962`. That artifact claims `repository_head=904560e44aaa0f6ae59f0834ad062b017666adaa`; `git cat-file -t` independently returned `could not get object info`. The ancestry relation is reproducible for available commits (`git merge-base --is-ancestor 8bb779d... e72d2b...` returned `rc=0`), but the exact head asserted by the resolution artifact is not available for review. | The available evidence supports a related ancestry fact, not the exact content-addressed head and 202-commit explanation asserted by M6A. Technical resolution cannot be accepted as independently reproduced. |
| 3 | Resolution of blocker 004, including “no invariant weakening,” is supported by exact immutable source. | **FAIL** | M6A SHA-256 above records current `source_compiler.py` as `5e1f56262810790966696a7720e93fa0bccaabfe4085e70fa76bb0fd64eb7186` and merge version as `0f41737c72b6f798f929623c2d650723166f45fc1c683082ea173e83f2aa16d5`. Independently, the available cited recovery commit `6787d636...` contains `source_compiler.py` SHA-256 `4747e3efb4bc9fdc925477f54f8fe4537fb267ebba64d609a5c5ed8b36a0384c`, not `5e1f...`; only the unavailable `4d1f22db...` object has `5e1f...`. The immutable available diff `24afce006...` → `4d1f22db...` is 35 insertions/13 deletions, but no exact current-head tree or independently bound invariant/test receipt is present. | The prose conclusion in M6A is not enough to prove the exact one-of-thirteen mismatch and its semantic safety. This is a source/reference-closure failure, not a hash mismatch in the four top-level successor files. |
| 4 | Exactly five blocker categories exist: reviewer, coherence, proof, ownership, portfolio. | **PASS for category labels; FAIL for complete blocker inventory** | Candidate ledger SHA-256 `9067c1181924f8480031558547361d21fc260740bed003a9ebb1b0a321e5617e`, lines 100–193, has exactly five unique ordered category strings. Independent probe reproduced `['reviewer','coherence','proof','ownership','portfolio']`. The duplicate in rank 1 prevents the stronger “no missing/duplicated/invented blocker” proposition. | Category count alone is insufficient acceptance evidence. |
| 5 | The old CL1 handoff remains `accepted_for_cl2=false`. | **PASS** | `23ed58c...:docs/critique-ledger/handoffs/cl1-contract-oracle.json`, blob `c73f994eb78b84cd025d75a619600e39df6068d3`, SHA-256 `ea55413bc05161212d1197f9d78679b89f2e0117a273f77f5880ec955fc1475d`; independent JSON probe returned `accepted_for_cl2.value=False`. | Correctly preserved and fail-closed. |
| 6 | Technical resolution is separated from procedural/external acceptance. | **PASS** | Candidate `raw-cl1-blocker-ledger.json:109-142,165-178` distinguishes resolved/derivative dispositions from required owner outputs and sets every category’s `blocks_t5_2_acceptance` to `true`; result `result.md:3,37-48` says formal owner acceptance remains pending. | Correct separation, subject to fixing ranks 1–3. |
| 7 | Four owner decisions remain explicitly unresolved and fail closed. | **PASS** | Candidate `raw-cl1-blocker-ledger.json:195-215` has four unique IDs `T5.1-OWNER-001` through `004`; all five category dispositions independently probe as blocking T5.2. Candidate manifest lines 10–16 reports count 4 and “not an owner acceptance receipt.” | Correctly prevents T5.2 acceptance, though explicit per-decision `status: pending` is not machine-bound. |
| 8 | No mutable v2 state/identity, generated state, budget, GLEK, notification ID, or forbidden successor identity was copied. | **PASS** | Candidate guardrails at `raw-cl1-blocker-ledger.json:9-15` prohibit copying; candidate contains source lineage/evidence references only and no successor allocation. The exact commit changes only the five T5.1 evidence/result files. | No forbidden successor material observed. |
| 9 | No artifact claims `accepted_for_cl2=true`. | **PASS** | Candidate JSON has `accepted_for_cl2: false` at `raw-cl1-blocker-ledger.json:35` and guardrail false at line 14. The only `true` text is normative future-gate wording (`T5.2 may derive...`) and the result explicitly says it cannot derive true. | No false acceptance claim. |
| 10 | The task caused no cloud/provider/Run Authority/Custody/WBC/marker mutation. | **PASS within the reviewed scope** | Exact commit diff is only `result.md`, `README.md`, `candidate-manifest.json`, `raw-cl1-blocker-ledger.json`, and `verify_raw_cl1_blockers.py`; no mutation-like path changed. Review commands were `git show`, hashing, JSON probes, ancestry checks, and the read-only verifier; no cloud/provider command was used. | No mutation found or performed. |
| 11 | Exact commit changes no active code lanes T0.0, T1.3, T1.8, or T1.10. | **PASS** | `git diff-tree --no-commit-id --name-only -r e72d2baf...^ e72d2baf...` returned only the five T5.1 evidence/result paths; none overlaps those lanes. | Lane isolation holds. |

## Hash and manifest mechanics

The exact-commit tree objects independently rehashed as follows (all working-tree
bytes also matched their archived bytes):

```text
result.md               blob 76d848436f07dee8a9ad5dd5b3ec6a066ec52588  sha256 96718f62c79b4c5a2d38929546740018a752c9505291d13ba05642c184e4e92c
README.md               blob 582a50452da28fe12ea587a66c7a8eed5fe39e5d  sha256 68d0231cf72dcec28f4e2604e9cc6c79158715798d18ce8757be1648eb35b37e
candidate-manifest.json blob b83620cdee4f5ee0e30762e67512b871bcf285eb  sha256 a9e28d77eb14abaf9d66bac626db8b5453195bd688305a9e3b9bf0061a89b423
raw-cl1-blocker-ledger.json blob 59947eca5212673c616d33ff05000e0d66420d1b sha256 9067c1181924f8480031558547361d21fc260740bed003a9ebb1b0a321e5617e
verify_raw_cl1_blockers.py blob 072dc2b54bdf92ab86eefc717443198acf827d34 sha256 fcfb13041a21f88d420f564f7d0d7bb6b900424d5e5036e953fcf68f11a5b247
```

Every six raw-source objects and four top-level successor objects declared by
the ledger was independently read from its declared commit and matched both
the declared Git blob and SHA-256:

```text
raw: handoff ea55413bc05161212d1197f9d78679b89f2e0117a273f77f5880ec955fc1475d
raw: reviewer_gate d39b1501657b1c80cc8ca9c052efca58366ce6719eb4db1dd9f6af0b30507296
raw: coherence bd7d07c69cba3f37e4f50f8e535effeaae97b00604c726cd50f1616a20536e2e
raw: proof_index 91bc7ca1cf150754de9764150a71941795598be6bd59c75cd21fea5f9cefc76e
raw: ownership aae3dc0b7f404b5cb3ce749f5407c43b92b608f71ea7675ecc624e7aa3d266a4
raw: portfolio 0bbd9ca61699ce6b0f19b812e0656d957a0f5589148109b3ace8f637f9754e0d
successor: m6a c69783608f3202490b2326c042f3c8457a0034ba6db41ee4fbb910f69c137962
successor: m5_receipts 33adf5382d77611aab4e76081ca33d16c14906c4254129e52bbe1fc80d477c69
successor: m5_chain 9388336ceac92fa942454b17930cd288b62f757a3816320b45190e1d9449ce57
successor: m5_attestation 77bc397d8a82edf3b74a8b60710563141192b6fc28ca03b16a39df27f9d3976f
```

The candidate manifest’s four listed artifact hashes also independently matched
their exact worktree bytes. Its counts (6 raw, 4 successor, 5 categories, 4
decisions) are internally correct, but the verifier does not validate semantic
blocker uniqueness or nested source-reference closure.

## Supplied verifier and independent probes

Supplied verifier, run from the exact clean worktree without mutation:

```sh
python -I evidence/critique-ledger-recovery/T5.1/verify_raw_cl1_blockers.py
```

Result: exit 0; `source_tree`, six raw artifacts, four successor artifacts,
five category labels, four decision IDs, and fail-closed claims all passed;
reported ledger SHA-256 was
`9067c1181924f8480031558547361d21fc260740bed003a9ebb1b0a321e5617e`.
This is only a hash/structure verifier, as its own output states.

Independent probes and meaningful results:

```sh
git merge-base --is-ancestor 8bb779dcaa08edcc92736eb265689ad894d8d839 e72d2baf892613cad391df1a86e4d04b3ff29547
# rc=0

git cat-file -t 904560e44aaa0f6ae59f0834ad062b017666adaa
# fatal: git cat-file: could not get object info

git show 6787d6363e8fc0603092913ae877db14f3b9fff8:arnold/workflow/source_compiler.py | shasum -a 256
# 4747e3efb4bc9fdc925477f54f8fe4537fb267ebba64d609a5c5ed8b36a0384c

git show 4d1f22dbbd20efb9c246ed461f65b3cd57d91090:arnold/workflow/source_compiler.py | shasum -a 256
# 5e1f56262810790966696a7720e93fa0bccaabfe4085e70fa76bb0fd64eb7186

git diff --stat 24afce006b9ad20391ac7af10ef67ea0b1774f9f 4d1f22dbbd20efb9c246ed461f65b3cd57d91090 -- arnold/workflow/source_compiler.py
# 1 file changed, 35 insertions(+), 13 deletions(-)
```

## Required corrections

1. Replace the active blocker inventory with five unique category records and
   one canonical blocker per decision. Preserve historical
   `OWNERSHIP-BLOCKER-002` only as an explicit non-counting alias of
   `PC-SCOPE-BLOCKER-001`; do not count or repeat it as an active ownership
   blocker. Add verifier checks for unique blocker IDs and semantic duplicate
   detection across categories.
2. Supply the immutable Git object/archive for the exact M6A
   `repository_head=904560e...`, or regenerate M6A against an available exact
   commit. Bind the complete 13-file comparison, the modifying commit, its
   parent/ancestry, and the relevant immutable diff/test evidence by SHA-256.
   Recompute all dependent ledger and manifest hashes. Do not rely on the M6A
   prose verdict alone.
3. Close nested reference closure: hash-bind the exact versions of every
   `m6-prerequisite-verification.json`, `m6-proof-index.json`, and
   `ownership-decision-record.json` cited inside M6A, and ensure they are the
   same source versions used to classify the blockers.
4. Add explicit per-decision `status: OWNER_DECISION_PENDING` (or equivalent)
   and fail-closed checks for all four owner IDs, while preserving
   `accepted_for_cl2=false` until those receipts are independently accepted.

This review does not mark T5.1 complete and does not authorize T5.2, cloud
mutation, provider calls, Run Authority/Custody/WBC changes, launch, or any
other external effect.
