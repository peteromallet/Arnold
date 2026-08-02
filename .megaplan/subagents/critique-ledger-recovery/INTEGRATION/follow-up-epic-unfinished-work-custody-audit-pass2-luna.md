# Follow-up epic unfinished-work custody audit — pass 2

Date: 2026-08-02

Auditor: Luna (read-only re-audit; this report is the only candidate-worktree
write)

Prior FAIL report SHA-256:
`a194b64209740ec41f7ce83f3ebfc1e30dae875ce0afe71f96a62c5bd3fddfc0`

## Verdict

**FAIL / REVISE — the candidate now fails launch safely and closes most prior
custody defects, but it is not yet a mechanically complete stable-handoff
capture.**

This verdict is about accepting and freezing the follow-up epic handoff, not
about launching v3. No cloud action is authorized or needed. The truthful state
is:

`FOLLOW_UP_EPIC_HANDOFF_NOT_ACCEPTED / CANARY_CHAIN_ABSENT / LAUNCH_FAILS_CLOSED`

## Frozen candidate identity

- Worktree:
  `/private/tmp/arnold-critique-recovery-follow-up-epic-20260802`
- Commit: `175d24ce7214338f8a112ea8d98b72799b82f04c`
- Tree: `5a9f26525b3b4a8e9a2e5772f38814ee4529277b`
- Candidate status before this report: clean
- Epic inventory: all 15 files under
  `.megaplan/initiatives/critique-ledger-post-relaunch-completion/` are tracked
  in HEAD; the filesystem inventory and `git ls-files` inventory match.
- The referenced future canary chain
  `.megaplan/initiatives/critique-ledger-safe-v3-canary/chain.yaml` does not
  exist. That is honest: it remains future work and the launch gate currently
  rejects it.

## Prior blockers that are closed

1. `briefs/m5-evidence-and-incident-closeout.md` no longer claims a T3.6
   release receipt exists. It explicitly describes it as a future prerequisite
   absent at epic-authoring time.
2. `briefs/f1-owner-storage-recovery-hardening.md` now describes an eventual
   independently accepted and installed Stage-A route rather than falsely
   claiming a current accepted route.
3. `supersession-index.json` content-addresses the current zero-recovery route
   and blocks the stale T1.5/T1.10-positive routes, the counterfactual T1.4 map,
   rejected T1.5 pass 3, rejected T1.10 candidate, and superseded provider
   predecessor. The recorded document/report hashes match the present copies.
4. `proof-map.json` distinguishes
   `T3.6/release-authority/` from
   `T3.6/administrative-closeout/`; it no longer uses one undifferentiated
   T3.6 proof path.
5. `chain.yaml` no longer accepts phrases. It requires
   `chain_completed + require_manifest` for the future canary and `git_tracked`
   for the entire follow-up epic directory. The installed implementation
   validates the prerequisite chain/state, chain/North-Star/brief/proof hashes,
   milestone records and validation receipts. For a directory, `git_tracked`
   checks HEAD membership recursively and rejects any status entry below it.

## Remaining blockers

### B1 — dirty custody is not exact or content-addressed

The T1.1 item in `custody-manifest.json` says
`DIRTY_PRESERVED_18_PATHS_6_PASS_1_FAIL`, and `UNFINISHED_WORK.md` repeats 18.
The frozen live worktree has **19** paths: 15 modified tracked paths plus four
untracked files. The recorded status SHA-256
`c560b7085db39c1a8ba6bf8862f2644d3b1f364dac03ac8a0352cad2ac8ce0d4`
correctly reproduces from `git status --porcelain=v1 -uall`; the prose/count is
wrong.

More importantly, the dirty snapshots do not bind untracked bytes.
`status_sha256` binds status/path rows and `worktree_diff_sha256` binds tracked
worktree diffs, but neither hashes the contents of T1.2's untracked
`orchestration/critique_attempts.py` nor T1.1's four untracked implementation
files. A file can therefore change without invalidating the recorded hashes.

Required repair:

- correct T1.1 to 19 paths;
- declare the canonical commands/encoding used for every status/index/worktree
  digest; and
- add a sorted per-path content manifest (mode, disposition and SHA-256), or an
  equivalent canonical archive digest, covering every untracked file in each
  dirty lane.

### B2 — custody disposition and evidence identities are incomplete/stale

The provider item records
`CLEAN_CANDIDATE_PENDING_INDEPENDENT_REVIEW`. Independent review now exists and
returned **FAIL / REVISE** for the same clean commit/tree, finding strict-schema,
capacity-result, SSH-transport and option-shaped-target blockers. Bind and use:

- report:
  `.megaplan/subagents/critique-ledger-recovery/PROVIDER/cloud-observation-preflight-independent-review-luna.md`
- report SHA-256:
  `84384d99578e0992a05ab11996d49cc753e343131c7583f483f232f7a5ddefa9`
- corrected disposition: rejected/not integration or predeploy authority,
  pending repair of B1-B4 in that review and a fresh independent review.

The T1.3 item also lacks an explicit worktree/custody-reference, status hash and
evidence identity, although it shares the T1.2 lane. README lines 82–83 and the
ledger lines 76–78 still call it independently accepted/accepted without the
manifest's essential qualifier **bounded Stage-A component only**. State that
scope in every human authority and make the item point explicitly to its exact
custody source.

Most evidence paths in `custody-manifest.json` have no evidence SHA-256, and
the exact candidate tree contains none of the referenced
`.megaplan/subagents/critique-ledger-recovery/...` evidence files. A stable
handoff must either track the referenced evidence or bind each external
evidence artifact by digest and durable custody location. At minimum this also
applies to the provider author/review reports and the T1.9 specification
(`9a604b05637d2f9eba54db6a6f42e488e2d2979105a6b0d1d6dcb5665688ad11`).

### B3 — the proof map cannot produce the promised completion manifest

The `safe-v3-canary-admission` key is not a milestone in this chain.
`build_completion_manifest()` iterates only `spec.milestones` and looks up
proofs by their exact labels, so that pseudo-milestone is silently ignored.
Consequently the T6.2 acceptance, deny receipts, host observation, v2 fence,
custody and supersession entries in that block are not bound by this chain's
completion manifest.

Every actual milestone maps directory names such as
`evidence/critique-ledger-recovery/T1.9/`. The generator requires each proof
entry to satisfy `proof_path.is_file()` and hashes that exact file. These
directory entries can never generate a completion manifest as written.

Required repair:

- put safe-canary admission artifacts in the future canary chain's own proof
  map under real canary milestone labels;
- list exact proof files, not directories, for every follow-up milestone;
- include every required validation receipt in the owning milestone's proof
  list; and
- run the real manifest generator/validator against a completed fixture to
  prove no pseudo-label or directory proof is silently lost.

### B4 — task subeffects remain contradictory

The T3.6 folder split is correct, but the briefs do not honor it.
`f2-admission-model-effect-release-closure.md` says F2 closes both
administrative T3.6 tickets and accepts T3 release/ticket evidence, while
`m5-evidence-and-incident-closeout.md` says F7 owns that same ticket-closing
subeffect. One accepted milestone could therefore imply an effect owned by the
other.

T8.3 is also mapped to the identical unspecialized directory in both F2 and F7.
F2 claims the permanent replay candidate gate while F7 claims T8.1–T8.4. Remove
the premature T8.3 completion claim from F2 or assign typed, non-overlapping
subeffects and exact proof files. A master task must not become complete merely
because one milestone produced one of its effects.

### B5 — T1.9 does not explicitly own the future canary chain and conformance gate

The absent canary chain is correctly not claimed as present, and the downstream
gate is fail-closed. But the T1.9 custody item only requires bounded
implementation, deny-before-mutation hostile tests, installed parity and
independent review. Neither it nor the epic explicitly requires T1.9 to deliver:

- the committed `.megaplan/initiatives/critique-ledger-safe-v3-canary/chain.yaml`;
- its closed, content-addressed proof map and completion manifest;
- an installed independent conformance validator/validation milestone that
  checks traceability, proof-map completeness, exact consumed/deferred sets,
  zero-recovery capability denial, evidence digests and runtime/owner identity;
  and
- the validator receipt as an exact proof file consumed by
  `require_manifest`.

Add those as explicit T1.9 acceptance deliverables. Do not add an empty chain or
claim the validator exists merely to satisfy the path; the current absence is
the correct state until the implementation and independent acceptance exist.

## Exact pass conditions

This audit can pass after one clean, committed successor candidate:

1. freezes every dirty path including untracked bytes and corrects T1.1's count;
2. records the provider review FAIL and content-addresses all custody evidence;
3. scopes T1.3 consistently as a bounded Stage-A component;
4. uses only real milestone labels and exact files in executable proof maps;
5. assigns T3.6 and T8.3 effects once, or by typed non-overlapping subeffects;
6. makes the canary chain and installed conformance validation explicit T1.9
   deliverables; and
7. proves the canary and follow-up manifest paths with the real generator and
   validator while keeping the absent/unaccepted canary fail-closed.

The supersession index, corrected Stage-A/T3.6 existence wording, tracked whole
epic, and `chain_completed + require_manifest` launch mechanism should be
preserved.
