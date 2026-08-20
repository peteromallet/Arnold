# T5.1 independent review — pass 3 (Luna)

Review date: 2026-08-02 CEST
Worktree: /private/tmp/arnold-critique-recovery-t5-1-20260802
Requested candidate: 7c254f7f0d15ba4e835a6fe7cae40b47d29ef7cd

## Verdict

Local candidate: HARD FAIL.

The exact checkout, artifact bytes, raw CL1 facts, and all 88 declared tamper
probes reproduce successfully. However, the verifier does not bind the
candidate HEAD and tree to the exact requested commit/tree. A read-only
in-memory hostile-input case supplied a different head and tree while keeping
the required parent, changed paths, and checkout bytes; verify_candidate_checkout
accepted it. The verifier therefore cannot substantiate its own
exact_candidate_parent_head_tree_and_paths claim for an exact candidate.

The actual checkout was independently pinned to the requested commit/tree/
parent below. That does not cure the verifier's accepted forged-head case.

Formal T5.1: NOT COMPLETE. The recovery plan still has T5.1 unchecked with
Evidence: _pending_. All four external owner decisions remain
OWNER_DECISION_PENDING. This review does not resolve any of them or authorize
T5.2, CL2, cloud activity, or a v3 launch.

## Requirements and prior artifacts read

Read through EOF:

- Recovery plan:
  /Users/peteromalley/Documents/Arnold/docs/arnold/critique-ledger-incident-prevention-and-durable-recovery-plan-2026-08-02.md
  SHA-256 edddb198701c7567325aac5827100321addbe9e7c5dd458c1329628e82472e0c.
  T5.1 is at lines 490-495; mandatory regression tests are at lines
  1620-1658.
- Pass-1 review:
  independent-review-pass1.md
  SHA-256 f954d8f61feacdb6637371491efce96d0a6279240cc9da3490ef57cf7f79093b.
- Pass-2 review:
  independent-review-pass2.md
  SHA-256 c0beb45e906270235616d83dd1a41c3a629730deea62512b83ec46a0e6547e63.
- Pass-2 repair result:
  t5-1-repair-pass2-result.md
  SHA-256 deb16dc36b67797af2484f671dc0dca54536d25176205f0e4845f2712aaacc88.
- This review brief:
  t5-1-independent-review-pass3-luna-brief.md
  SHA-256 b2334223a763c9b8dd9eb95eb7712d25e8ae1fab603eb461e1d9c78354bc2cce.

The relevant plan requirement is: resolve the raw CL1
reviewer/coherence/proof/ownership/portfolio blockers. It does not authorize
turning candidate evidence into owner acceptance.

## Exact Git identity and cleanliness

Commands:

~~~
git rev-parse --show-toplevel
git status --porcelain=v1
git rev-parse HEAD
git rev-parse HEAD^{tree}
git rev-parse HEAD^1
git cat-file commit 7c254f7f0d15ba4e835a6fe7cae40b47d29ef7cd
git diff-tree --no-commit-id --name-status -r 7c254f7f0d15ba4e835a6fe7cae40b47d29ef7cd^ 7c254f7f0d15ba4e835a6fe7cae40b47d29ef7cd
git diff-tree --check 7c254f7f0d15ba4e835a6fe7cae40b47d29ef7cd^
git fsck --no-progress --no-dangling --no-reflogs --unreachable
~~~

Results:

~~~
status: empty
HEAD: 7c254f7f0d15ba4e835a6fe7cae40b47d29ef7cd
tree: 27e7b22ef0d7f3faeaa6b7cbcd63aabb2872d7e9
parent: c703628d728096573df82b22af9f46c70a7c28d3
subject: docs(critique-ledger): harden T5.1 evidence verifier
parent tree: 5094ab7750aa474cbe1c220d24e18e8aa4a9acfb
diff-tree --check: PASS
fsck: PASS; no reported unreachable/dangling objects
changed paths: exactly 7, all T5.1 evidence/reporting paths
~~~

The seven exact Git blobs and independent SHA-256 values:

| Path | Git blob | SHA-256 |
|---|---|---|
| .megaplan/subagents/critique-ledger-recovery/T5.1/result.md | 166dbbee99ee8b8d2c10d091f15978b813a367bd | d4f85dba3054d9d366f043093f30bd44019b53ca6155aaf184fdfbc1f1344b14 |
| evidence/critique-ledger-recovery/T5.1/README.md | 73469a327c5ae7a85367abcf355bff8b80798797 | 9047adf79915751c546a8b5a153c8dadab56c5901aa64ca3e03e46291e17b851 |
| evidence/critique-ledger-recovery/T5.1/candidate-manifest.json | 52c21a05dad0aee7ea41006d749ccd9a95944774 | a5a340c3bdaeaecf535f009a9fda3ca37017e3cb27c287fcf997dd817d19c256 |
| evidence/critique-ledger-recovery/T5.1/raw-cl1-blocker-ledger.json | d3c3180406706d2b09cf5d599d4438cf4b24c609 | ab748eb288c2e219815afdda338bd4eed8f6cd71547adb43b393aa6d1f654052 |
| evidence/critique-ledger-recovery/T5.1/technical-resolution.json | b0532d46eb6c00417c30017983fb6fea312d9284 | 36f0d0129d7ddcf02b135fc46747b7cd222664d406ba3699c33a2539d65f6e98 |
| evidence/critique-ledger-recovery/T5.1/verification-receipt.json | f139742513c97a5f9e5e04065b1038e6ac586f96 | 0bce23950be01f7535d4acf2c9cff66b4cf16fb93c571a0217ddbe083e520636 |
| evidence/critique-ledger-recovery/T5.1/verify_raw_cl1_blockers.py | 45569e09303cbdddcc38f2ed63ed47929b4e5b8e | ed410ade83c36069b17945dd4ea5ff0e0ba9aa8aadbf5258bfdd7de0ebd9d895 |

For every row, git show candidate:path, working-tree bytes, and git hash-object
agreed.

## Supplied verifier baseline

Commands:

~~~
python -I evidence/critique-ledger-recovery/T5.1/verify_raw_cl1_blockers.py
ruff check evidence/critique-ledger-recovery/T5.1/verify_raw_cl1_blockers.py
~~~

Result: exit 0; Ruff reported All checks passed!. The verifier printed:

~~~
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
~~~

Reproduced output hashes:

~~~
manifest:             a5a340c3bdaeaecf535f009a9fda3ca37017e3cb27c287fcf997dd817d19c256
ledger:               ab748eb288c2e219815afdda338bd4eed8f6cd71547adb43b393aa6d1f654052
technical-resolution: 36f0d0129d7ddcf02b135fc46747b7cd222664d406ba3699c33a2539d65f6e98
verification receipt: 0bce23950be01f7535d4acf2c9cff66b4cf16fb93c571a0217ddbe083e520636
verifier:             ed410ade83c36069b17945dd4ea5ff0e0ba9aa8aadbf5258bfdd7de0ebd9d895
ordered probe names: 1a77bc608c6c6d93f06be74a407025f6297d25bf37d23f8207d97701a9312cbe
~~~

## Independent bound-artifact rehashes

The independent script used Git plumbing and hashlib, did not import or call
the supplied verifier, and rehashed all declared raw, successor, nested, and
WBC objects.

Raw source commit:

~~~
commit 23ed58c1074dbd78d75e0bc8008376426225de51
tree   fd87e14beaae45667a42b758a3634f76c41dd9da
parent d365ef68592b930c7f55c7f40f9b90af8cd03c06
source is not an ancestor of recovery base: PASS
~~~

Six raw source objects (all matched Git blob and SHA-256 claims):

| Role | Path | Git blob | SHA-256 |
|---|---|---|---|
| handoff | docs/critique-ledger/handoffs/cl1-contract-oracle.json | c73f994eb78b84cd025d75a619600e39df6068d3 | ea55413bc05161212d1197f9d78679b89f2e0117a273f77f5880ec955fc1475d |
| reviewer_gate | docs/critique-ledger/evidence/cl1-semantic-loop-gate.json | 8d0b55ae1ce3a23f9d95ba597c8d6ca6fa152e99 | d39b1501657b1c80cc8ca9c052efca58366ce6719eb4db1dd9f6af0b30507296 |
| coherence | evidence/m6-prerequisite-verification.json | f797f777033859752172351e03c4f7760d59d194 | bd7d07c69cba3f37e4f50f8e535effeaae97b00604c726cd50f1616a20536e2e |
| proof_index | evidence/m6-proof-index.json | f649e961b22b4408967885652fd8abc863f72b60 | 91bc7ca1cf150754de9764150a71941795598be6bd59c75cd21fea5f9cefc76e |
| ownership | evidence/ownership-decision-record.json | 9ab3165d4623c1602b9ed6956b1ffc45a2889797 | aae3dc0b7f404b5cb3ce749f5407c43b92b608f71ea7675ecc624e7aa3d266a4 |
| portfolio | evidence/pc-scope-decision.json | cbcba12e93893f62133ed9138b118394460f865d | 0bbd9ca61699ce6b0f19b812e0656d957a0f5589148109b3ace8f637f9754e0d |

Four successor objects:

~~~
M5 receipt reconciliation: commit 6787d6363e8fc0603092913ae877db14f3b9fff8
  blob 1dc473bcbaa52a90ad053ed7f515438124de318a
  sha256 33adf5382d77611aab4e76081ca33d16c14906c4254129e52bbe1fc80d477c69
M5 chain verification: commit 6787d6363e8fc0603092913ae877db14f3b9fff8
  blob a984eaa76e81d55fa039ad9b770c267c4d179874
  sha256 9388336ceac92fa942454b17930cd288b62f757a3816320b45190e1d9449ce57
M5 final attestation: commit 6787d6363e8fc0603092913ae877db14f3b9fff8
  blob 839aed9c8c254cfca83c261da5b967aafa14f92b
  sha256 77bc397d8a82edf3b74a8b60710563141192b6fc28ca03b16a39df27f9d3976f
technical-resolution: WORKTREE_CANDIDATE
  sha256 36f0d0129d7ddcf02b135fc46747b7cd222664d406ba3699c33a2539d65f6e98
~~~

Historical M6A:

~~~
publication commit 4e480fec168c7130c6754f0f0293e6b0d0ac90a8
tree                13b16e776053be76103b475848795c767cac588f
path                evidence/m6a-prerequisite-resolution.json
blob                3348f4dbdb9c670d07a41c94fe92bf54f0085569
sha256              c69783608f3202490b2326c042f3c8457a0034ba6db41ee4fbb910f69c137962
claimed repository head: 904560e44aaa0f6ae59f0834ad062b017666adaa
claimed head availability: absent; candidate correctly does not admit it
~~~

Three nested references, derived from the M6A object's ref fields and matched
exactly in order:

~~~
prerequisite_verification_ref -> evidence/m6-prerequisite-verification.json
  blob e888b761d12ae0a4a4a246c4706784073027e443
  sha256 f978eb902d7da23ff5068ba2a9aa2d2020c0826d2a0a8babaccf9a338d03587a
proof_index_ref -> evidence/m6-proof-index.json
  blob 4f8e4b1427802c66591f6f2c98df14471f85fa8a
  sha256 40cc3f7d976a1f1ece4773f7e5f514217065f02ef6408eb96b8f82ca33896255
ownership_decision_ref -> evidence/ownership-decision-record.json
  blob a7214e78a0450c6abe5c531e6751129c29572b5d
  sha256 02524b300cfa59e06636db1f1ce9395cb546bc9b01a409f1c32c1afe11707e29
~~~

Blocker 003 independently reproduced M5 commit/tree
8bb779dcaa08edcc92736eb265689ad894d8d839 /
ca3f0102b5c1ab7ed1d1a619c8c4932d989ab23d, recovery-base commit/tree
6787d6363e8fc0603092913ae877db14f3b9fff8 /
83a22fc5f5930cbcbe5a439129706bb90bb28a92, ancestry, count 578, and the
attestation hash above.

Blocker 004 independently reproduced baseline commit/tree
24afce006b9ad20391ac7af10ef67ea0b1774f9f /
d163ea0434eeb22b5cb3911e301fb59a0ab83672, modifying commit/tree/parent
4d1f22dbbd20efb9c246ed461f65b3cd57d91090 /
10acf480a6e8575f9dd7bb9f3312b07edecb7f57 /
69a4f8135c463a82ac0e89a908ec95852153f419, exact one-path diff, diff SHA-256
1de018abd3d73dc486da8962867bf9f0dc13d7d95f0dc1fd50f286445c379c89, and the
isolated AST result: 9 stable rows, 27 mappings, front-half override, and
non-front-half filtering.

The 13-file comparison was independently flattened from M6A categories in
canonical order. It had 13 unique paths, 12 matches, and exactly one mismatch:
arnold/workflow/source_compiler.py. Every row's baseline/modified Git blob and
SHA-256 matched both the candidate and M6A values.

## Independent re-probe of all 88 declared tamper classes

The harness loaded the verifier by absolute path after chdir('/tmp'), copied
each JSON object in memory, applied one mutation, and invoked the corresponding
validator. No repository file was changed.

~~~
ledger validators:             19/19 rejected
technical validators:          50/50 rejected
manifest/receipt validators:    19/19 rejected
TOTAL:                         88/88 rejected; names unique and order-preserved
~~~

The exact declared probe-name sequence was compared with the receipt; its
ordered-name SHA-256 was
1a77bc608c6c6d93f06be74a407025f6297d25bf37d23f8207d97701a9312cbe.

The categories covered, in exact receipt order, were:

~~~
19 ledger:
duplicate_active_id, duplicate_active_semantic_key, reordered_categories,
duplicate_category, forged_active_blocker_id,
forged_alias_and_target_semantic_identity, missing_alias_target,
counting_historical_alias, forged_raw_source_commit, forged_raw_source_tree,
forged_raw_source_parent, duplicate_owner_decision, missing_owner_decision,
extra_owner_decision, reordered_owner_decisions, nonpending_owner_decision,
claimed_accepted_owner_decision, pending_owner_receipt_forged, extra_ledger_key

50 technical:
omit_all_nested_m6a_refs, omit_one_nested_m6a_ref, extra_nested_m6a_ref,
duplicate_nested_m6a_ref, reordered_nested_m6a_refs, substituted_nested_m6a_path,
forged_nested_m6a_commit, forged_nested_m6a_blob, forged_nested_m6a_digest,
forged_historical_claimed_head, forged_historical_artifact_commit,
forged_historical_artifact_tree, forged_historical_artifact_blob,
forged_historical_artifact_digest, historical_m6a_claim_admitted,
blocker_003_uses_unavailable_head, forged_m5_bound_commit, forged_m5_bound_tree,
forged_recovery_base_commit, forged_m5_commit_count,
forged_successor_attestation_digest, omit_wbc_path, extra_wbc_path,
duplicate_wbc_path_count_substitution, reordered_wbc_paths,
substituted_wbc_path, forged_wbc_baseline_blob, forged_wbc_baseline_digest,
forged_wbc_modified_blob, forged_wbc_modified_digest,
forged_wbc_baseline_commit, forged_wbc_baseline_tree,
forged_wbc_modifying_commit, forged_wbc_modifying_tree,
forged_wbc_modifying_parent, forged_wbc_modifying_subject,
forged_wbc_diff_digest, forged_wbc_diff_stat, decoupled_parent_binding,
decoupled_semantic_binding, forged_probe_id, forged_probe_source_commit,
forged_probe_source_blob, forged_probe_source_digest,
forged_probe_constants_digest, forged_probe_row_count,
forged_probe_mapping_count, omitted_probe_assertions, forged_probe_result_digest,
extra_technical_key

19 manifest/receipt:
manifest_missing_artifact, manifest_extra_artifact, manifest_duplicate_artifact,
manifest_reordered_artifacts, manifest_forged_artifact_digest,
manifest_forged_source_commit, manifest_forged_parent_commit,
manifest_forged_changed_paths, manifest_forged_tamper_count, manifest_extra_key,
receipt_replay_old_verifier_digest, receipt_forged_ledger_digest,
receipt_forged_technical_digest, receipt_missing_check, receipt_reordered_checks,
receipt_forged_count, receipt_missing_tamper_probe,
receipt_claims_t5_2_authorized, receipt_extra_key
~~~

## Additional hostile cases

Independent extra cases beyond the declared 88 all rejected:

~~~
unknown extra raw object:                 REJECTED
unknown extra successor object:           REJECTED
stale-but-valid raw path/hash swap:       REJECTED
stale-but-valid WBC path/hash swap:       REJECTED
Unicode/NFKC path alias:                  REJECTED
relative path alias:                      REJECTED
absolute path confusion:                  REJECTED
nested relative path confusion:           REJECTED
nested absolute path confusion:           REJECTED
manifest self-artifact cycle:             REJECTED
receipt check-cycle marker:               REJECTED
self-referential successor evidence:      REJECTED
partial M6A read:                         REJECTED
corrupt M6A read:                         REJECTED
symlink/type replacement status case:     REJECTED (dirty Git status)
~~~

No filesystem mutation was performed for the symlink case. The harness supplied
the Git status that a tracked type/mode replacement would produce, and
verify_candidate_checkout failed closed before reading candidate bytes. All
seven candidate paths are currently Git mode 100644.

Different-working-directory command:

~~~
cd /tmp
python -I /private/tmp/arnold-critique-recovery-t5-1-20260802/evidence/critique-ledger-recovery/T5.1/verify_raw_cl1_blockers.py
~~~

Result: exit 0, passed=true, exact candidate head
7c254f7f0d15ba4e835a6fe7cae40b47d29ef7cd, and 88 probes.

## Remaining hard failure: forged candidate HEAD/tree accepted

The following read-only in-memory case patched only the verifier's input
functions. It advertised a different 40-hex head and tree, retained the exact
repair parent and expected path list, and returned the real checkout bytes for
the advertised head. The verifier has no check that the advertised head exists,
is a commit, has the advertised tree, or equals the exact requested candidate.

~~~
fake HEAD:  1111111111111111111111111111111111111111
fake tree:  2222222222222222222222222222222222222222
parent:     c703628d728096573df82b22af9f46c70a7c28d3
paths:      exact 7-path allowlist
result:     ACCEPTED_BYPASS
~~~

The gap is in verify_raw_cl1_blockers.py:994-1014: it derives HEAD and
HEAD^{tree} but only constrains the parent, parent tree, changed paths, clean
status, and bytes. The receipt does not bind the emitted final head/tree, and
the manifest has no final head/tree field. The actual exact commit was
externally pinned above, but the requested hostile-verifier contract requires
this identity binding to fail closed.

## Raw CL1 factual audit

The five active blocker facts were checked against exact immutable source
objects:

| Blocker | Exact source facts | Result |
|---|---|---|
| Reviewer | 23ed...:docs/critique-ledger/evidence/cl1-semantic-loop-gate.json:62-66 has reviewed=false, empty reviewer and timestamp, pending sign-off. The handoff repeats this at :371-377 and :419-421. | PASS; remains pending. |
| Coherence | 23ed...:evidence/m6-prerequisite-verification.json:10-21 lists the three missing completion_verdict.json files and status INCOHERENT; handoff repeats it at :379-383. | PASS; remains pending. |
| Proof | 23ed...:evidence/m6-proof-index.json:5-9 has validation_passed=false and two prerequisite errors; aggregate state is INCOHERENT at :298-312. | PASS; remains pending. |
| Ownership | 23ed...:evidence/ownership-decision-record.json:1248-1268 says all three M1-M3 receipts have accepted:false and requires three accepted receipts with canonical divergence zero. | PASS; remains pending. |
| Portfolio | 23ed...:evidence/pc-scope-decision.json:9-18,57-63 records the machine-generated program_counter default and a blocked human portfolio approval requirement. | PASS; remains pending. |

The cross-category duplicate is factually canonicalized: raw ownership
OWNERSHIP-BLOCKER-002 at 23ed...:1271-1282 and raw portfolio
PC-SCOPE-BLOCKER-001 at 23ed...:pc-scope-decision.json:57-63 describe the
same human PC-scope decision; the candidate counts only the portfolio blocker.
The immutable handoff remains accepted_for_cl2.value=false at
23ed...:docs/critique-ledger/handoffs/cl1-contract-oracle.json:411-439.

The historical M6A unavailable head is exact at
4e480...:evidence/m6a-prerequisite-resolution.json:5; its three nested refs
are at :173-175. The WBC historical hashes and source-compiler investigation
are at :10-113. These matched the independent Git rehashes.

The source evidence cites
tests/arnold_pipelines/megaplan/test_zero_write_mutation_gate.py::TestSemanticLoopZeroWrite.
The exact source file contains that helper class at line 1089, but it has no
collected test_* method; the targeted command returned no tests found for that
node. The complete file nevertheless passed independently:

~~~
python -I -m pytest -q tests/arnold_pipelines/megaplan/test_zero_write_mutation_gate.py
~~~

Result: 23 passed in 0.37s. This is a citation-quality limitation in the
immutable source evidence, not an owner decision or completion claim.

## Owner-decision and authority boundary

The exact ledger contains, in order:

~~~
T5.1-OWNER-001  OWNER_DECISION_PENDING  accepted=false  receipt=null
T5.1-OWNER-002  OWNER_DECISION_PENDING  accepted=false  receipt=null
T5.1-OWNER-003  OWNER_DECISION_PENDING  accepted=false  receipt=null
T5.1-OWNER-004  OWNER_DECISION_PENDING  accepted=false  receipt=null
~~~

They remain, respectively: independent CL1 review; CL1/Run Authority decision
on M5 successor proof; human portfolio approval or explicit exclusion; and a
fresh current zero-blocker ownership/proof decision. No owner decision was
resolved here.

No cloud/provider command, owner mutation, checklist edit, code/evidence edit,
commit amendment, or external authority action was performed. The only file
written by this review is this result artifact.

## Final disposition

The exact candidate bytes and source facts are reproducible, but the verifier's
accepted forged candidate-head/tree binding is a hard local failure under the
requested hostile-input standard. Formal T5.1 remains incomplete independently
of that local verdict because the plan's evidence is pending and all four
external owner decisions remain unresolved.

