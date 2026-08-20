# T5.1 Independent Review — Pass 2

## Overall verdict: FAIL

The exact candidate bytes repair the factual defects found in pass 1: the current
ledger has five semantically unique active blockers, treats
`OWNERSHIP-BLOCKER-002` as a non-counting alias, rejects the unavailable
`904560e…` claim, regenerates blocker 003 against available objects, contains the
complete historical 13-file blocker-004 comparison, closes the three nested M6A
references, and leaves exactly four owner decisions pending and fail-closed.

The candidate nevertheless fails the evidence-only acceptance contract because
the supplied verifier and its `passed=true` receipt are not omission- or
identity-resistant. Independent in-memory tamper probes proved that the verifier
accepts all three nested M6A references being deleted, accepts one required WBC
path being omitted and another duplicated while still reporting a complete
13-file comparison, and accepts forged source/alias/probe/parent-binding
identities. The receipt's corresponding closure claims are therefore stronger
than the checks that produce them.

This is candidate evidence only. This review does not mark T5.1 complete, grant
owner acceptance, or authorize T5.2.

## Review anchors

- Reviewed commit: `c703628d728096573df82b22af9f46c70a7c28d3`.
- Independently rehashed Git commit object: exact match to `c703628d728096573df82b22af9f46c70a7c28d3`.
- Independently rehashed tree object: `5094ab7750aa474cbe1c220d24e18e8aa4a9acfb`.
- Parent: `e72d2baf892613cad391df1a86e4d04b3ff29547`.
- Worktree: `/private/tmp/arnold-critique-recovery-t5-1-20260802`.
- `HEAD` was the reviewed commit; `git status --porcelain`, unstaged diff, and
  staged diff were empty.
- Master contract SHA-256:
  `fa174f33bc98b68504d8a2813a645e399015421c542ec9d43c374671dc11afb8`.
- Pass-1 review SHA-256:
  `f954d8f61feacdb6637371491efce96d0a6279240cc9da3490ef57cf7f79093b`.
- The master checklist still marks T5.1 `Evidence: _pending_` and does not
  authorize T5.2.

The exact commit changes seven paths, all confined to T5.1 evidence/reporting:

```text
.megaplan/subagents/critique-ledger-recovery/T5.1/result.md
evidence/critique-ledger-recovery/T5.1/README.md
evidence/critique-ledger-recovery/T5.1/candidate-manifest.json
evidence/critique-ledger-recovery/T5.1/raw-cl1-blocker-ledger.json
evidence/critique-ledger-recovery/T5.1/technical-resolution.json
evidence/critique-ledger-recovery/T5.1/verification-receipt.json
evidence/critique-ledger-recovery/T5.1/verify_raw_cl1_blockers.py
```

No active T0.0, T1.3, T1.8, or T1.10 lane, checklist, cloud specification,
provider surface, Run Authority, Custody, WBC authority record, marker, or
runtime source is changed by this commit.

## Ranked findings

### 1. FAIL — nested-reference omission is accepted while the verifier reports closure

`verify_technical()` only loops over
`historical_m6a_nested_reference_closure` (`verify_raw_cl1_blockers.py:280-281`).
It does not require cardinality three, unique roles, the exact three paths, the
M6A artifact's actual `*_ref` values, or the publication commit. Replacing the
entire list with `[]` made `verify_technical()` return successfully.

The main verifier then emits hard-coded `nested_reference_count: 3` at lines
499-503. The checked-in receipt likewise claims
`historical_m6a_nested_reference_closure`, `passed=true`, count 3. Thus an omitted
closure can be reported as a three-reference closure.

The current commit's three entries are factually correct when independently
checked; the failure is that the candidate verifier/receipt does not establish
that fact.

### 2. FAIL — the “complete 13-file comparison” is not omission-resistant

The verifier checks the length and the aggregate match/mismatch counts, but not
path uniqueness and not equality to the historical M6A path inventory
(`verify_raw_cl1_blockers.py:333-358`). An independent tamper probe replaced
`arnold/workflow/boundary_conformance.py` with a second copy of
`arnold/workflow/boundary_compatibility.py`. The list still contained 13 entries,
12 matches, and one `source_compiler.py` mismatch; `verify_technical()` accepted
it.

This permits a required historical file to be omitted while the verifier and
receipt continue to report `wbc_file_count: 13`. The current commit's list is in
fact the exact unique historical 13-path list, but that was established only by
the independent audit below.

### 3. FAIL — forged identities and cross-field bindings are accepted

Independent tamper probes also produced these accepted bypasses:

- Changed `historical_m6a_context.claimed_repository_head` from the actual M6A
  value `904560e44aaa0f6ae59f0834ad062b017666adaa` to forty zeroes. The verifier
  checks only that the self-declared value is unavailable; it never compares it
  to the exact M6A JSON object.
- Changed the portfolio blocker's and alias's semantic key together to a forged
  value and changed the reviewer blocker ID to `FORGED-REVIEWER-ID`.
  `validate_inventory()` plus `verify_raw_alias_source()` accepted the mutation.
  Categories and uniqueness are checked, but the five canonical active IDs and
  semantic identities are not anchored to the raw sources.
- Changed `source_compiler_parent_binding.parent_commit` from the modifying
  commit's actual parent to the WBC baseline, with that baseline's correct blob
  and SHA-256. The verifier accepted the decoupled “parent binding.”
- Changed `exact_commit_probe.required_stable_rows` and
  `required_export_mappings` to 999 and deleted its declared assertions. The
  verifier ignored these fields and accepted the artifact.
- Forged the modifying subject, diff-stat prose, resolution conclusion, and set
  `historical_904560e_claim_used=true`. These claimed fields are not checked.

The current fields independently match their sources. The failure is that the
receipt presents them as verifier-bound when multiple identity and semantic
bindings are actually self-declared or ignored.

### 4. PASS — pass-1 blocker inventory defect is factually repaired

The current ledger's exact ordered active inventory is:

```text
reviewer   CL1-REVIEWER-SIGNOFF-001
coherence  CL1-M6-COHERENCE-001
proof      CL1-M6-PROOF-001
ownership  OWNERSHIP-BLOCKER-001
portfolio  PC-SCOPE-BLOCKER-001
```

All five blocker IDs and all five semantic keys are unique, and all five set
`blocks_t5_2_acceptance=true`. The raw ownership and portfolio objects prove that
`OWNERSHIP-BLOCKER-002` and `PC-SCOPE-BLOCKER-001` describe the same human
portfolio PC-scope decision. The ledger now represents the former exactly once
as:

```text
OWNERSHIP-BLOCKER-002 -> PC-SCOPE-BLOCKER-001
status=HISTORICAL_NON_COUNTING_ALIAS
counting=false
```

`OWNERSHIP-BLOCKER-003` and `004` are separate resolved, non-counting technical
dispositions. The supplied verifier correctly rejects reordered/duplicate
categories, duplicate active IDs/semantic keys, bad alias targets, semantic-key
mismatch between alias and target, and a counting alias. It does not, however,
reject the jointly forged semantic identity described in finding 3.

### 5. PASS — blocker 003 is regenerated without admitting unavailable `904560e…`

The historical M6A object is available at publication commit
`4e480fec168c7130c6754f0f0293e6b0d0ac90a8`, tree
`13b16e776053be76103b475848795c767cac588f`, path
`evidence/m6a-prerequisite-resolution.json`, blob
`3348f4dbdb9c670d07a41c94fe92bf54f0085569`, SHA-256
`c69783608f3202490b2326c042f3c8457a0034ba6db41ee4fbb910f69c137962`.
It claims repository head
`904560e44aaa0f6ae59f0834ad062b017666adaa`; `git cat-file -e
904560e...^{commit}` failed. The candidate correctly sets
`historical_m6a_claim_admitted=false`,
`claimed_repository_head_available=false`, and
`historical_904560e_claim_used=false`.

The regenerated exact objects are:

- M5 bound commit `8bb779dcaa08edcc92736eb265689ad894d8d839`, tree
  `ca3f0102b5c1ab7ed1d1a619c8c4932d989ab23d`.
- Canonical recovery base `6787d6363e8fc0603092913ae877db14f3b9fff8`,
  tree `83a22fc5f5930cbcbe5a439129706bb90bb28a92`.
- M5 is an ancestor of the recovery base; the independently reproduced
  `8bb779d..6787d63` count is 578.
- Successor final attestation blob
  `839aed9c8c254cfca83c261da5b967aafa14f92b`, SHA-256
  `77bc397d8a82edf3b74a8b60710563141192b6fc28ca03b16a39df27f9d3976f`.

This resolves only the candidate technical lineage/attestation branch. It does
not supply owner decision `T5.1-OWNER-002` or `004`.

### 6. PASS — the current blocker-004 object has the exact historical 13-file binding

Independent code flattened the exact M6A `boundary`, `runtime`, `schema`, and
`support` lists and required exact ordered equality with the candidate list. The
current list has 13 unique paths, 12 exact matches, and one mismatch:

| Path | Baseline blob / SHA-256 | Modified blob / SHA-256 | Status |
|---|---|---|---|
| `arnold/workflow/boundary_compatibility.py` | `78260e730285119609bd432a90b87a619c62a56c` / `8be489c8d3b967842ce1301318e31c51a78db2d3049fa703eb8bb313745e47f4` | same | match |
| `arnold/workflow/boundary_conformance.py` | `cdee92ee9218228f27c58b0e6725d23a80aa23dc` / `bf58b340449e07b994fd7b58f81cd70b87096abc4966d161eb008b4f9999d6d1` | same | match |
| `arnold/workflow/boundary_evidence.py` | `7baa17005a99f064129cc789a041e32fd3dc35f4` / `cca8cefa761f80d31fca781a218af61d97c588a5d5f8afc63d632f262d9f68ed` | same | match |
| `arnold/workflow/boundary_templates.py` | `24e76d511fb8b575eac9e76d085befebd2db7581` / `1f794664a6947977e5bd92692562e12c0776fd1e304b40a7f643cf60dd8eba48` | same | match |
| `arnold/workflow/execution_attempt_ledger.py` | `2fdb23afa94d0ec1adba386b9643a09b3a9c4692` / `8d2ca188ad4dbd606bfe629c4871ab67d9a15efa92751372cd3a125b335a496b` | same | match |
| `arnold/workflow/durable_refs.py` | `3264de57ecaef8b140cc7c0b6c4658bc7c9bd308` / `83ec86f19f41cd065635259e4e60e0451d84b4617ac860c31a90e02676112673` | same | match |
| `arnold/workflow/payload_policy.py` | `85eda6818c91f7412f32823681f6458121b4aadc` / `0d4eb2a634b3105c003a005902063b4d811f50840d3a60e06c55f825d5328d27` | same | match |
| `arnold_pipelines/megaplan/workflows/contract_to_producer_matrix.json` | `e28db03c13b55f47e096a817be961527d5e18296` / `5778c4064f53ada1b884d50225d95ab12bb9f487dfa98586e8cc488ebd33d386` | same | match |
| `arnold_pipelines/megaplan/workflows/source_to_owner_matrix.json` | `d4046ca1e9eb0c4fc7a7596cc29a7e879f39cfa0` / `d03f3302c63edb03706b3a5ef36ef50e8ccb17a5ed5c65802be0cb35479c1965` | same | match |
| `arnold_pipelines/megaplan/workflows/support_manifest.json` | `d7e3486db6927f7d91ccabc2aa9e448209515dce` / `0170c7bc5e7bcd6b34929cf2459f1a0d8dda42976b5d0e1463c304711bc8f381` | same | match |
| `arnold/workflow/source_compiler.py` | `0990e1ed49740e6063627a2c74ef6be982ba84cf` / `0f41737c72b6f798f929623c2d650723166f45fc1c683082ea173e83f2aa16d5` | `a4401d42a3583c9c9c4190f017c33060687641a9` / `5e1f56262810790966696a7720e93fa0bccaabfe4085e70fa76bb0fd64eb7186` | mismatch |
| `arnold_pipelines/megaplan/workflows/boundary_contracts.py` | `06a765fc1fd425c7d7234775a3f9dfcff31c8cf0` / `de7fc79155413d083de15203a9024580bca78e28c733955ab5c1f11c38776b4d` | same | match |
| `docs/arnold/workflow-boundary-contracts.md` | `424a256113a29ad7c11a7616ff206b4dd03ec701` / `dac3175af043806d9052a76a37fc62f2b47b91dad3127b8d4dadcac893cd42a6` | same | match |

The independently reproduced identity and semantic bindings are:

- Baseline `24afce006b9ad20391ac7af10ef67ea0b1774f9f`, tree
  `d163ea0434eeb22b5cb3911e301fb59a0ab83672`.
- Modifying commit `4d1f22dbbd20efb9c246ed461f65b3cd57d91090`,
  tree `10acf480a6e8575f9dd7bb9f3312b07edecb7f57`, parent
  `69a4f8135c463a82ac0e89a908ec95852153f419`, subject
  `fix(workflow): retain missing boundary contract diagnostics`.
- The baseline is an ancestor of the modifying commit; the modifying commit is
  an ancestor of recovery base `6787d636…`.
- The modifying commit changes exactly
  `arnold/workflow/source_compiler.py`.
- Exact binary diff SHA-256:
  `1de018abd3d73dc486da8962867bf9f0dc13d7d95f0dc1fd50f286445c379c89`.
- Diff stat: `1 file changed, 35 insertions(+), 13 deletions(-)`.
- Exact semantic-evidence blob
  `eedb57cb05a40534702b1f231602f618519bbefa`, SHA-256
  `58502d12d0b13c54b8c2e226ae09d1271097a9e05abf299924240d27a3f59077`.
- Independent isolated AST execution, which did not import or call the supplied
  verifier, reproduced all nine stable rows and 27 export mappings, confirmed
  caller-supplied critique mappings override the stable rows, and confirmed a
  non-front-half `execute` contract is ignored.

These facts repair pass-1's factual source-closure failure, but finding 2 means
the supplied verifier does not itself prove the list is complete.

### 7. PASS — current nested M6A references are exact

At the M6A publication commit `4e480fec…`, the artifact's actual three path
references resolve as follows:

| Role/path | Blob | SHA-256 |
|---|---|---|
| `prerequisite_verification_ref` → `evidence/m6-prerequisite-verification.json` | `e888b761d12ae0a4a4a246c4706784073027e443` | `f978eb902d7da23ff5068ba2a9aa2d2020c0826d2a0a8babaccf9a338d03587a` |
| `proof_index_ref` → `evidence/m6-proof-index.json` | `4f8e4b1427802c66591f6f2c98df14471f85fa8a` | `40cc3f7d976a1f1ece4773f7e5f514217065f02ef6408eb96b8f82ca33896255` |
| `ownership_decision_ref` → `evidence/ownership-decision-record.json` | `a7214e78a0450c6abe5c531e6751129c29572b5d` | `02524b300cfa59e06636db1f1ce9395cb546bc9b01a409f1c32c1afe11707e29` |

The current technical-resolution entries match those exact roles, paths,
commit, blobs, and hashes. This was independently established; the supplied
verifier's cardinality/identity omission remains finding 1.

### 8. PASS — exactly four owner decisions remain explicitly unresolved

The ledger has exactly ordered, unique IDs `T5.1-OWNER-001` through `004`.
Every one has:

```text
status=OWNER_DECISION_PENDING
accepted=false
receipt=null
```

The five active blockers reference exactly that four-ID set, with proof and
ownership both depending on owner decision 004. All five remain blocking for
T5.2. The supplied verifier correctly rejects missing, duplicate, reordered,
non-pending, accepted, and receipt-bearing pending owner decisions (the receipt
case is checked by the function even though it is not one of the nine named
self-tamper probes).

### 9. PASS — no acceptance, successor authorization, copied v2 identity, or mutation

The exact candidate JSON contains no `accepted_for_cl2: true`,
`t5_2_authorized: true`, or `v3_launch_authorized: true`. The one textual
`accepted_for_cl2=true` occurrence is a normative future completion rule and
does not claim present acceptance. No GLEK, notification ID, budget ID,
successor session/plan/branch/worktree, provider PR identity, generated v2
state, or successor allocation field is present. The README and result explicitly
deny completion/authorization/mutation.

The review performed only local Git reads, hashing, JSON/AST probes, the supplied
local verifier, and in-memory tamper tests. It made no cloud/provider/authority
call and no active-lane mutation.

## Exact artifact and source rehashes

All reviewed checkout bytes matched the exact archived bytes at `c703628d…`:

```text
result.md                 blob a21e611cdadee2a59ecdfeafe4aafd33bacf2da6
                          sha256 c4d42fc61fa06d563035d2290765ec442a06c50bc7c1a825dc5ea68555aefe9f
README.md                 blob 85d74849949e50c669280eeff7df96e4b6496de1
                          sha256 13c7075a37d36ec81bffeeb2ebf04a33c631e1ff49a2955c08af99d1e95df3b8
candidate-manifest.json   blob 20772181c4c21b4483ceea83add976310a582513
                          sha256 9a928747b2a48a344f91bb0d75a91a62ec0bdb5375b8101c7732468bc89fd32e
raw-cl1-blocker-ledger    blob e4c67551a49a925c0338dbf2702ea725559e31ab
                          sha256 2196a9c7f25fccce024f0ca28ac23e37e94c65a45aa33575ee0e0a294f941931
technical-resolution     blob 90faadbcc28723ccb32bdfd95943640795e3601f
                          sha256 c9633e2d4e72187351f7d31fa0996ffccc89854d5298a896be045c74f0cc37c6
verification-receipt     blob cfc74364c18b3e1364af163aaf503f6322a08386
                          sha256 40290c74d29cb7d4ddb6a2dc98efe033fd072a8b2e2cc8cc83b375406d14a190
verifier                  blob e0449dfb64592b232d35c9d3f57c6170a5828c09
                          sha256 7cd62fa0dba374aa317bfc0fdad65401e8e0af849202a64af47570bd455bfe62
```

The manifest has the exact six unique non-self artifact paths and every listed
SHA-256 matches. Excluding the manifest from its own artifact list avoids a
direct self-hash cycle; the exact Git commit anchors the manifest itself. The
ledger's `WORKTREE_CANDIDATE` technical reference is also non-circular in this
clean exact-commit review because both files are independently anchored by the
commit and manifest. The supplied verifier itself reads the worktree and does
not bind `HEAD` to a declared candidate commit, so that clean/exact-commit check
must remain an external review requirement.

Raw source commit `23ed58c1074dbd78d75e0bc8008376426225de51`
reproduces tree `fd87e14beaae45667a42b758a3634f76c41dd9da` and parent
`d365ef68592b930c7f55c7f40f9b90af8cd03c06`. It is not an ancestor of
recovery base `6787d636…`, matching the ledger. Its six raw objects are:

```text
handoff        blob c73f994eb78b84cd025d75a619600e39df6068d3 sha256 ea55413bc05161212d1197f9d78679b89f2e0117a273f77f5880ec955fc1475d
reviewer_gate  blob 8d0b55ae1ce3a23f9d95ba597c8d6ca6fa152e99 sha256 d39b1501657b1c80cc8ca9c052efca58366ce6719eb4db1dd9f6af0b30507296
coherence      blob f797f777033859752172351e03c4f7760d59d194 sha256 bd7d07c69cba3f37e4f50f8e535effeaae97b00604c726cd50f1616a20536e2e
proof_index    blob f649e961b22b4408967885652fd8abc863f72b60 sha256 91bc7ca1cf150754de9764150a71941795598be6bd59c75cd21fea5f9cefc76e
ownership      blob 9ab3165d4623c1602b9ed6956b1ffc45a2889797 sha256 aae3dc0b7f404b5cb3ce749f5407c43b92b608f71ea7675ecc624e7aa3d266a4
portfolio      blob cbcba12e93893f62133ed9138b118394460f865d sha256 0bbd9ca61699ce6b0f19b812e0656d957a0f5589148109b3ace8f637f9754e0d
```

The successor references independently reproduced as:

```text
m5 receipt reconciliation  blob 1dc473bcbaa52a90ad053ed7f515438124de318a sha256 33adf5382d77611aab4e76081ca33d16c14906c4254129e52bbe1fc80d477c69
m5 chain verification      blob a984eaa76e81d55fa039ad9b770c267c4d179874 sha256 9388336ceac92fa942454b17930cd288b62f757a3816320b45190e1d9449ce57
m5 final attestation       blob 839aed9c8c254cfca83c261da5b967aafa14f92b sha256 77bc397d8a82edf3b74a8b60710563141192b6fc28ca03b16a39df27f9d3976f
candidate technical        blob 90faadbcc28723ccb32bdfd95943640795e3601f sha256 c9633e2d4e72187351f7d31fa0996ffccc89854d5298a896be045c74f0cc37c6
```

The capture-context hashes also reproduce against the named current master
artifacts:

```text
T0.2 manifest  c45030bd29c57d1eb0d1694c705aebb3dd55ca04fa3b612ad0d287e32e4dc791
T0.4 inventory 2984a983ae7a307d02b6d36cb53ab42122e5d9ad63d5d5eb0ff8d0c89ff5bff8
```

Those two capture files are not members of the reviewed candidate commit; this
review verified the content-addressed current master copies. The supplied T5.1
verifier does not check these capture-context fields.

## Supplied verifier and independent probes

The supplied command:

```sh
python -I evidence/critique-ledger-recovery/T5.1/verify_raw_cl1_blockers.py
```

exited 0 and reported ledger SHA-256
`2196a9c7f25fccce024f0ca28ac23e37e94c65a45aa33575ee0e0a294f941931`,
technical-resolution SHA-256
`c9633e2d4e72187351f7d31fa0996ffccc89854d5298a896be045c74f0cc37c6`,
nine negative tamper probes, and `passed=true`.

Independent code did not import or call that verifier. It rehashed the Git
commit/tree objects, exact candidate blobs, all raw/successor/nested references,
the M6A object, the two blocker-003 commits and attestation, all 26 baseline and
modified file blobs/hashes, the modifying parent and binary diff, and executed
the exact historical function/constant blobs. Its current-byte result was PASS.

A separate adversarial in-memory harness imported only the supplied validator
functions to test their rejection behavior. Results:

```text
REJECTED: reordered categories
REJECTED: duplicate category
REJECTED: reordered owner decisions
REJECTED: duplicate owner decision

ACCEPTED BYPASS: all three nested M6A references omitted
ACCEPTED BYPASS: required WBC path omitted and another path duplicated
ACCEPTED BYPASS: historical claimed-head identity forged
ACCEPTED BYPASS: alias semantic identity and active reviewer ID forged
ACCEPTED BYPASS: declared exact-probe counts/assertions forged
ACCEPTED BYPASS: source-compiler parent binding decoupled
ACCEPTED BYPASS: technical subject/stat/conclusion/904-use fields forged
```

The verifier does not read or trust `verification-receipt.json` as an input,
which avoids one direct self-approval cycle. However, it also does not validate
the receipt's check list or counts; the manifest merely hash-binds the receipt's
bytes. Several counts in verifier output are hard-coded rather than derived.
Consequently the checked-in receipt is a static candidate claim whose material
closure propositions require an independent verifier.

## Required corrections

1. Require exactly three unique nested roles and exact path equality to the
   three `*_ref` values read from the exact M6A artifact at its exact publication
   commit. Derive the reported nested count from the validated list.
2. Require the exact unique 13-path list read from the M6A artifact; reject
   omissions, duplicates, additions, and reorderings. Derive all receipt counts
   from validated data.
3. Anchor the canonical five active blocker IDs and semantic identities to the
   raw source fields, not only to category order and self-declared semantic keys.
   Add negative probes for jointly forged alias/target semantics and forged
   active IDs.
4. Compare the candidate's historical M6A claimed head, baseline, modifying
   commit, and paths to the exact historical M6A JSON. Enforce all declared
   parent/semantic/probe cross-bindings or remove unchecked claims from the
   receipt-bearing artifact.
5. Validate the candidate manifest's declared counts/source/recovery fields and
   the verification receipt's check set/counts against recomputed results. Bind
   the verifier to a clean exact candidate commit/tree rather than implicitly to
   mutable worktree bytes.
6. Add negative tamper probes for every accepted bypass above and prove each
   fails closed before issuing another `passed=true` candidate receipt.

Until those corrections are independently reviewed, T5.1 remains incomplete;
T5.2, CL2 acceptance, v3 identity allocation, cloud/provider activity, active
lane changes, launch, and all authority mutation remain unauthorized.
